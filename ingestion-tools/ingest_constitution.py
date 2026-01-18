#!/usr/bin/env python3
"""
Constitution Ingestion Script - Neo4j Only
==========================================

This script ONLY handles ingesting pre-parsed Constitution data into Neo4j.
It loads the parsed structure from JSON and creates the legal ontology.

Usage:
    python ingest_constitution.py [--json-file constitution_parsed.json]

Prerequisites:
    1. Run parse_constitution.py first to create JSON file
    2. Neo4j should be running and configured
    3. OpenAI API key for embeddings

Author: Constitution Processing Pipeline
"""

import sys
import json
import asyncio
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.graph_service import get_graph_service
from src.repositories.neo4j_repository import neo4j_repository
from src.utils.embedding_client import embedding_client
from src.config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ConstitutionIngestionRunner:
    """Handles Constitution ingestion into Neo4j from parsed JSON."""

    def __init__(self, json_file: Optional[str] = None):
        if json_file is None:
            self.json_file = str(Path(__file__).parent / "output" / "constitution_parsed.json")
        else:
            self.json_file = json_file
        self.graph_service = get_graph_service()
        self.neo4j_repo = neo4j_repository
        self.embedding_client = embedding_client
        self.constitution_id = "Constitution of India"

    async def run_ingestion(self) -> bool:
        """Run the complete ingestion process."""
        print("🏛️  CONSTITUTION INGESTION - Neo4j Legal Ontology Creation")
        print("=" * 70)

        try:
            # Step 1: Load parsed JSON
            parsed_data = self._load_parsed_json()
            if not parsed_data:
                return False

            # Step 2: Verify prerequisites
            if not self._check_prerequisites():
                return False

            # Step 3: Clean existing data
            await self._clean_existing_data()

            # Step 4: Create Constitution Statute (root)
            constitution_id = await self._create_constitution_statute(parsed_data)

            # Step 5: Create Parts hierarchy
            parts_created = await self._create_parts_hierarchy(parsed_data, constitution_id)

            # Step 6: Create Article Provisions
            articles_created = await self._create_article_provisions(parsed_data, constitution_id)

            # Step 7: Create Schedule Provisions
            schedules_created = await self._create_schedule_provisions(parsed_data, constitution_id)

            # Step 8: Create cross-reference relationships
            references_created = await self._create_cross_references(parsed_data)

            # Step 9: Create semantic chunks for search
            chunks_created = await self._create_semantic_chunks(parsed_data, constitution_id)

            # Step 10: Create legal concepts
            concepts_created = await self._create_legal_concepts()

            # Step 11: Print final summary
            self._print_final_summary({
                "constitution_id": constitution_id,
                "parts_created": parts_created,
                "articles_created": articles_created,
                "schedules_created": schedules_created,
                "references_created": references_created,
                "chunks_created": chunks_created,
                "concepts_created": concepts_created
            })

            print("\n✅ Constitution ingestion completed successfully!")
            print("🔄 Run 'python validate_constitution.py' to verify the graph")

            return True

        except Exception as e:
            logger.error(f"Ingestion failed: {e}", exc_info=True)
            print(f"\n❌ Ingestion failed: {e}")
            return False

    def _load_parsed_json(self) -> Optional[dict]:
        """Load parsed Constitution data from JSON."""
        print("📄 Step 1: Loading parsed Constitution data...")

        if not Path(self.json_file).exists():
            print(f"   ❌ JSON file not found: {self.json_file}")
            print("   Run 'python parse_constitution.py' first to create this file")
            return None

        try:
            with open(self.json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            file_size = Path(self.json_file).stat().st_size / 1024 / 1024
            print(f"   ✅ Loaded {self.json_file} ({file_size:.1f} MB)")

            # Validate structure
            required_keys = ['legal_document', 'parsing_metadata']
            missing = [key for key in required_keys if key not in data]
            if missing:
                print(f"   ❌ Invalid JSON structure, missing: {missing}")
                return None

            legal_doc = data['legal_document']
            print(f"   📊 Document: {legal_doc['name']}")
            print(f"   📊 Provisions: {legal_doc['total_provisions']}")
            print(f"   📊 Parts: {len(legal_doc['hierarchy']['parts'])}")

            return data

        except Exception as e:
            print(f"   ❌ Failed to load JSON: {e}")
            return None

    def _check_prerequisites(self) -> bool:
        """Check Neo4j and embedding prerequisites."""
        print("🔧 Step 2: Checking Neo4j and embedding prerequisites...")

        # Check Neo4j connection
        try:
            self.graph_service.verify_connection()
            print("   ✅ Neo4j connection verified")
        except Exception as e:
            print(f"   ❌ Neo4j connection failed: {e}")
            return False

        # Check embedding client
        try:
            test_embedding = self.embedding_client.generate_single_embedding("test")
            if len(test_embedding) == 0:
                raise ValueError("Empty embedding returned")
            print("   ✅ Embedding client working")
        except Exception as e:
            print(f"   ❌ Embedding client failed: {e}")
            return False

        return True

    async def _clean_existing_data(self):
        """Clean any existing Constitution data."""
        print("🧹 Step 3: Cleaning existing Constitution data...")

        cleanup_queries = [
            # Remove relationships first
            """
            MATCH (s:Statute {name: $constitution_name})-[r]-()
            DELETE r
            """,
            # Remove provisions
            """
            MATCH (p:Provision {statute_name: $constitution_name})
            DETACH DELETE p
            """,
            # Remove parts
            """
            MATCH (part:Part {constitution: $constitution_name})
            DETACH DELETE part
            """,
            # Remove statute
            """
            MATCH (s:Statute {name: $constitution_name})
            DELETE s
            """,
            # Remove legal concepts
            """
            MATCH (lc:LegalConcept {document_source: $constitution_name})
            DETACH DELETE lc
            """,
            # Remove constitution chunks
            """
            MATCH (c:Chunk)
            WHERE c.chunk_id CONTAINS "constitution"
            DETACH DELETE c
            """
        ]

        for i, query in enumerate(cleanup_queries):
            try:
                self.graph_service.execute_query(query, {"constitution_name": self.constitution_id})
                print(f"   ✅ Cleanup step {i+1}/{len(cleanup_queries)} completed")
            except Exception as e:
                print(f"   ⚠️ Cleanup step {i+1} failed: {e}")

    async def _create_constitution_statute(self, parsed_data: dict) -> str:
        """Create the root Constitution Statute node."""
        print("🏛️ Step 4: Creating Constitution Statute node...")

        legal_doc = parsed_data['legal_document']

        query = """
        MERGE (constitution:Statute {name: $name})
        SET constitution.year = $year,
            constitution.type = $type,
            constitution.total_articles = $total_provisions,
            constitution.total_parts = $total_parts,
            constitution.total_schedules = $total_schedules,
            constitution.indexed_at = datetime()
        RETURN constitution.name as constitution_id
        """

        params = {
            "name": legal_doc['name'],
            "year": legal_doc['year'],
            "type": legal_doc['document_type'],
            "total_provisions": legal_doc['total_provisions'],
            "total_parts": len(legal_doc['hierarchy']['parts']),
            "total_schedules": len(legal_doc['hierarchy']['schedules'])
        }

        result = self.graph_service.execute_query(query, params)
        constitution_id = result[0]['constitution_id']
        print(f"   ✅ Created Constitution Statute: {constitution_id}")

        return constitution_id

    async def _create_parts_hierarchy(self, parsed_data: dict, constitution_id: str) -> int:
        """Create Part nodes and their relationships."""
        print("📖 Step 5: Creating Parts hierarchy...")

        parts = parsed_data['legal_document']['hierarchy']['parts']
        parts_created = 0

        for part in parts:
            query = """
            MATCH (constitution:Statute {name: $constitution_name})
            MERGE (part:Part {number: $number, constitution: $constitution_name})
            SET part.title = $title,
                part.full_name = $full_name
            MERGE (constitution)-[:HAS_PART]->(part)
            RETURN part.number as part_number
            """

            params = {
                "constitution_name": constitution_id,
                "number": part['number'],
                "title": part['title'],
                "full_name": f"Part {part['number']}: {part['title']}"
            }

            self.graph_service.execute_query(query, params)
            parts_created += 1

        print(f"   ✅ Created {parts_created} Parts")
        return parts_created

    async def _create_article_provisions(self, parsed_data: dict, constitution_id: str) -> int:
        """Create Article Provision nodes with embeddings."""
        print("📜 Step 6: Creating Article Provisions with embeddings...")

        provisions = parsed_data['legal_document']['hierarchy']['provisions']
        articles = [p for p in provisions if p['provision_type'] == 'ARTICLE']
        articles_created = 0

        # Process in batches for efficiency
        batch_size = 10
        for i in range(0, len(articles), batch_size):
            batch = articles[i:i + batch_size]

            print(f"   🔄 Processing articles {i+1}-{min(i+batch_size, len(articles))} of {len(articles)}...")

            # Generate embeddings for batch
            article_texts = [article['text'] for article in batch]
            embeddings = self.embedding_client.generate_embeddings(article_texts)

            # Create nodes with embeddings
            for article, embedding in zip(batch, embeddings):
                await self._create_single_article(article, embedding, constitution_id)
                articles_created += 1

        print(f"   ✅ Created {articles_created} Article Provisions")
        return articles_created

    async def _create_single_article(self, article: dict, embedding: List[float], constitution_id: str):
        """Create a single article provision with embedding."""
        query = """
        MATCH (constitution:Statute {name: $constitution_name})
        OPTIONAL MATCH (part:Part {number: $part_number, constitution: $constitution_name})

        MERGE (provision:Provision {id: $provision_id})
        SET provision.number = $number,
            provision.title = $title,
            provision.text = $text,
            provision.part = $part_number,
            provision.statute_name = $constitution_name,
            provision.provision_type = $provision_type,
            provision.embedding = $embedding,
            provision.indexed_at = datetime()

        MERGE (constitution)-[:HAS_PROVISION]->(provision)

        WITH provision, part
        WHERE part IS NOT NULL
        MERGE (part)-[:CONTAINS]->(provision)

        RETURN provision.id as provision_id
        """

        params = {
            "constitution_name": constitution_id,
            "provision_id": article['id'],
            "number": article['number'],
            "title": article['title'],
            "text": article['text'],
            "part_number": article['part_number'],
            "provision_type": article['provision_type'],
            "embedding": embedding
        }

        self.graph_service.execute_query(query, params)

    async def _create_schedule_provisions(self, parsed_data: dict, constitution_id: str) -> int:
        """Create Schedule Provision nodes."""
        print("📋 Step 7: Creating Schedule Provisions...")

        provisions = parsed_data['legal_document']['hierarchy']['provisions']
        schedules = [p for p in provisions if p['provision_type'] == 'SCHEDULE']
        schedules_created = 0

        for schedule in schedules:
            # Generate embedding
            embedding = self.embedding_client.generate_single_embedding(schedule['text'])

            query = """
            MATCH (constitution:Statute {name: $constitution_name})
            MERGE (provision:Provision {id: $provision_id})
            SET provision.number = $number,
                provision.title = $title,
                provision.text = $text,
                provision.statute_name = $constitution_name,
                provision.provision_type = $provision_type,
                provision.embedding = $embedding,
                provision.indexed_at = datetime()
            MERGE (constitution)-[:HAS_SCHEDULE]->(provision)
            RETURN provision.id as provision_id
            """

            params = {
                "constitution_name": constitution_id,
                "provision_id": schedule['id'],
                "number": schedule['number'],
                "title": schedule['title'],
                "text": schedule['text'],
                "provision_type": schedule['provision_type'],
                "embedding": embedding
            }

            self.graph_service.execute_query(query, params)
            schedules_created += 1

        print(f"   ✅ Created {schedules_created} Schedule Provisions")
        return schedules_created

    async def _create_cross_references(self, parsed_data: dict) -> int:
        """Create REFERENCES relationships between provisions."""
        print("🔗 Step 8: Creating cross-references...")

        internal_refs = parsed_data['legal_document']['internal_references']
        references_created = 0

        for source_id, target_ids in internal_refs.items():
            for target_id in target_ids:
                query = """
                MATCH (source:Provision {id: $source_id})
                MATCH (target:Provision {id: $target_id})
                MERGE (source)-[:REFERENCES]->(target)
                RETURN count(*) as refs_created
                """

                params = {
                    "source_id": source_id,
                    "target_id": target_id
                }

                result = self.graph_service.execute_query(query, params)
                if result and result[0]['refs_created'] > 0:
                    references_created += 1

        print(f"   ✅ Created {references_created} cross-references")
        return references_created

    async def _create_semantic_chunks(self, parsed_data: dict, constitution_id: str) -> int:
        """Create semantic chunks for search."""
        print("🔍 Step 9: Creating semantic chunks for search...")

        provisions = parsed_data['legal_document']['hierarchy']['provisions']
        chunks_created = 0

        # Create collection for constitutional provisions
        collection_id = "constitution-golden-source"
        user_id = "system"

        self.neo4j_repo.create_user_collection(user_id, collection_id)

        for provision in provisions:
            # Create document and chunk for this provision
            document_id = f"constitution-{provision['id'].lower()}"
            chunk_id = f"{document_id}-chunk-001"

            # Get or create embedding
            embedding = self.embedding_client.generate_single_embedding(provision['text'])

            # Create chunk using existing repository method
            chunk_data = [{
                "chunk_id": chunk_id,
                "text": provision['text'],
                "embedding": embedding,
                "chunk_type": "CONCEPT",
                "chapter_title": provision['part_number'] or "",
                "section_title": provision['title'],
                "page_start": provision.get('page_start'),
                "page_end": provision.get('page_end'),
                "key_terms": [provision['number'], provision['title']],
                "has_equations": False,
                "has_diagrams": False
            }]

            # Index through repository
            self.neo4j_repo.index_chunks(
                user_id=user_id,
                collection_id=collection_id,
                file_id=document_id,
                file_name=f"Constitution-{provision['id']}",
                chunks=chunk_data,
                source_type="constitution"
            )

            # Link chunk to provision
            await self._link_chunk_to_provision(chunk_id, provision['id'])

            chunks_created += 1

        print(f"   ✅ Created {chunks_created} semantic chunks")
        return chunks_created

    async def _link_chunk_to_provision(self, chunk_id: str, provision_id: str):
        """Link chunk to its corresponding Provision node."""
        query = """
        MATCH (chunk:Chunk {chunk_id: $chunk_id})
        MATCH (provision:Provision {id: $provision_id})
        MERGE (chunk)-[:REPRESENTS]->(provision)
        """

        params = {
            "chunk_id": chunk_id,
            "provision_id": provision_id
        }

        self.graph_service.execute_query(query, params)

    async def _create_legal_concepts(self) -> int:
        """Create LegalConcept nodes for major constitutional themes."""
        print("⚖️ Step 10: Creating Legal Concepts...")

        constitutional_concepts = [
            {
                "name": "Fundamental Rights",
                "description": "Basic human rights guaranteed by the Constitution",
                "part": "III",
                "article_range": "12-35"
            },
            {
                "name": "Directive Principles of State Policy",
                "description": "Guidelines for governance and policy-making",
                "part": "IV",
                "article_range": "36-51"
            },
            {
                "name": "Emergency Provisions",
                "description": "Constitutional provisions for national emergency",
                "part": "XVIII",
                "article_range": "352-360"
            },
            {
                "name": "Federalism",
                "description": "Distribution of powers between Union and States",
                "part": "XI",
                "article_range": "245-263"
            },
            {
                "name": "Judicial Review",
                "description": "Power of judiciary to review legislative and executive actions",
                "part": "V",
                "article_range": "124-147"
            }
        ]

        concepts_created = 0

        for concept in constitutional_concepts:
            query = """
            MERGE (legal_concept:LegalConcept {name: $name})
            SET legal_concept.description = $description,
                legal_concept.constitutional_part = $part,
                legal_concept.article_range = $article_range,
                legal_concept.document_source = $document_source
            """

            params = {
                "name": concept["name"],
                "description": concept["description"],
                "part": concept["part"],
                "article_range": concept["article_range"],
                "document_source": self.constitution_id
            }

            self.graph_service.execute_query(query, params)

            # Connect concept to relevant provisions
            await self._connect_concept_to_provisions(concept)
            concepts_created += 1

        print(f"   ✅ Created {concepts_created} Legal Concepts")
        return concepts_created

    async def _connect_concept_to_provisions(self, concept: dict):
        """Connect LegalConcept to relevant Provision nodes."""
        query = """
        MATCH (concept:LegalConcept {name: $concept_name})
        MATCH (provision:Provision)
        WHERE provision.part = $part
          AND provision.statute_name = $statute_name
        MERGE (concept)-[:DERIVED_FROM]->(provision)
        """

        params = {
            "concept_name": concept["name"],
            "part": concept["part"],
            "statute_name": self.constitution_id
        }

        self.graph_service.execute_query(query, params)

    def _print_final_summary(self, results: dict):
        """Print final ingestion summary."""
        print("\n📊 Step 11: Final Ingestion Summary")
        print("=" * 50)

        print(f"   Constitution: {results['constitution_id']}")
        print(f"   Parts created: {results['parts_created']}")
        print(f"   Articles created: {results['articles_created']}")
        print(f"   Schedules created: {results['schedules_created']}")
        print(f"   Cross-references: {results['references_created']}")
        print(f"   Semantic chunks: {results['chunks_created']}")
        print(f"   Legal concepts: {results['concepts_created']}")
        print(f"   Total provisions: {results['articles_created'] + results['schedules_created']}")

        print(f"\n   ✅ Ingestion completed at: {datetime.now().isoformat()}")


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Ingest Constitution into Neo4j")
    parser.add_argument(
        "--json-file",
        default=None,
        help="JSON file with parsed Constitution data"
    )
    return parser.parse_args()


async def main():
    """Main function to run Constitution ingestion."""
    args = parse_arguments()

    runner = ConstitutionIngestionRunner(json_file=args.json_file)
    success = await runner.run_ingestion()

    if success:
        print("\n🎉 SUCCESS! Constitution ingested into Neo4j.")
        print("Next step: Run 'python validate_constitution.py' to verify")
    else:
        print("\n❌ FAILED! Check the error messages above.")
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)