#!/usr/bin/env python3
"""
BNS (Bharatiya Nyaya Sanhita) Ingestion Script - Neo4j
=====================================================

This script handles ingesting parsed BNS data into Neo4j as a public collection.
It loads the parsed BNS structure from JSON and creates the legal ontology.

Usage:
    python ingest_bns.py [--json-file bns_parsed_new.json]

Prerequisites:
    1. Run parse_bns.py first to create JSON file
    2. Neo4j should be running and configured
    3. OpenAI API key for embeddings

Author: BNS Processing Pipeline
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
from src.repositories.neo4j_repository import Neo4jRepository
from src.utils.embedding_client import embedding_client
from src.models.api_models import HierarchicalChunk, TopicMetadata, ChunkMetadata, ChunkType
from src.config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BNSIngestionRunner:
    """Handles BNS ingestion into Neo4j from parsed JSON."""

    def __init__(self, json_file: Optional[str] = None):
        if json_file is None:
            self.json_file = str(Path(__file__).parent / "output" / "bns_parsed_new.json")
        else:
            self.json_file = json_file
        self.graph_service = get_graph_service()
        self.neo4j_repo = Neo4jRepository()
        self.embedding_client = embedding_client

        # BNS constants
        self.collection_id = "bns-golden-source"
        self.user_id = "system"  # Public collection, system user
        self.file_id = "bns-act-2023"

    def load_parsed_data(self) -> Dict[str, Any]:
        """Load parsed BNS data from JSON file."""
        logger.info(f"Loading parsed BNS data from {self.json_file}")

        if not Path(self.json_file).exists():
            raise FileNotFoundError(f"Parsed JSON file not found: {self.json_file}")

        with open(self.json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        logger.info(f"Loaded BNS data: {data['total_sections']} sections, {data['total_chapters']} chapters")
        return data

    def check_existing_data(self) -> bool:
        """Check if BNS data already exists in Neo4j."""
        try:
            query = """
            MATCH (d:Document {file_id: $file_id})
            RETURN d.file_id as file_id, d.indexed_at as indexed_at
            """
            result = self.graph_service.execute_query(query, {"file_id": self.file_id})

            if result:
                indexed_at = result[0]["indexed_at"]
                logger.info(f"BNS already indexed at: {indexed_at}")
                return True
            return False

        except Exception as e:
            logger.error(f"Error checking existing data: {e}")
            return False

    def clear_existing_data(self):
        """Clear existing BNS data from Neo4j."""
        logger.info("Clearing existing BNS data...")

        try:
            # Delete all BNS chunks and document
            query = """
            MATCH (d:Document {file_id: $file_id})-[:HAS_CHUNK]->(c:Chunk)
            DETACH DELETE c, d
            """
            self.graph_service.execute_query(query, {"file_id": self.file_id})

            logger.info("Existing BNS data cleared successfully")

        except Exception as e:
            logger.error(f"Error clearing existing data: {e}")
            raise

    def generate_embeddings(self, chunks: List[Dict[str, Any]]) -> List[List[float]]:
        """Generate embeddings for BNS chunks."""
        logger.info(f"Generating embeddings for {len(chunks)} BNS chunks")

        texts = [chunk["text"] for chunk in chunks]

        try:
            embeddings = self.embedding_client.generate_embeddings(texts)
            logger.info(f"Generated {len(embeddings)} embeddings")
            return embeddings

        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise

    def prepare_chunk_objects(self, chunks: List[Dict[str, Any]], embeddings: List[List[float]]) -> List[HierarchicalChunk]:
        """Prepare HierarchicalChunk objects for Neo4j ingestion (following constitution pattern)."""
        chunk_objects = []

        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            # Create document ID
            section_num = chunk.get("section_number", f"s{i+1}")
            document_id = f"bns-{section_num}"

            # Create TopicMetadata (following constitution pattern)
            topic_metadata = TopicMetadata(
                chapter_num=None,  # BNS uses Roman numerals, so use None
                chapter_title=f"Chapter {chunk.get('chapter_number', 'Unknown')}" if chunk.get("chapter_number") else "Chapter Unknown",
                section_num=chunk.get("section_number", ""),
                section_title=chunk.get("section_title", ""),
                page_start=chunk.get("page_start"),
                page_end=chunk.get("page_end")
            )

            # Create ChunkMetadata
            chunk_metadata = ChunkMetadata(
                chunk_type=ChunkType.CONCEPT,  # BNS sections are legal concepts
                topic_id=f"BNS-{section_num}",
                key_terms=[f"Section {section_num}", chunk.get("section_title", "")],
                has_equations=False,
                has_diagrams=False
            )

            # Create HierarchicalChunk object
            chunk_obj = HierarchicalChunk(
                chunk_id=chunk["chunk_id"],
                document_id=document_id,
                topic_metadata=topic_metadata,
                chunk_metadata=chunk_metadata,
                text=chunk["text"],
                embedding_vector=embedding
            )

            chunk_objects.append(chunk_obj)

        logger.info(f"Created {len(chunk_objects)} HierarchicalChunk objects for indexing")
        return chunk_objects

    def index_bns_data(self, chunk_objects: List[HierarchicalChunk], embeddings: List[List[float]]) -> bool:
        """Index BNS data into Neo4j as a public collection."""
        logger.info("Starting BNS data indexing into Neo4j...")

        try:
            # Create BNS collection as public
            success = self.neo4j_repo.create_user_collection(
                user_id=self.user_id,
                collection_id=self.collection_id
            )

            if not success:
                logger.warning("Collection creation returned false, but continuing...")

            # Index chunks using HierarchicalChunk objects
            success = self.neo4j_repo.index_chunks(
                chunks=chunk_objects,
                embeddings=embeddings,
                user_id=self.user_id,
                collection_id=self.collection_id,
                file_id=self.file_id,
                file_name="Bharatiya Nyaya Sanhita 2023",
                source_type="legal_act"
            )

            if success:
                logger.info("✅ BNS data indexed successfully!")
                return True
            else:
                logger.error("❌ BNS indexing failed")
                return False

        except Exception as e:
            logger.error(f"Error indexing BNS data: {e}")
            raise

    def mark_as_public(self):
        """Mark BNS collection and chunks as public."""
        logger.info("Marking BNS data as public...")

        try:
            # Mark collection as public
            query = """
            MATCH (c:Collection {collection_id: $collection_id})
            SET c.is_public = true
            """
            self.graph_service.execute_query(query, {"collection_id": self.collection_id})

            # Mark all BNS chunks as public
            query = """
            MATCH (c:Chunk {collection_id: $collection_id})
            SET c.is_public = true
            """
            self.graph_service.execute_query(query, {"collection_id": self.collection_id})

            logger.info("✅ BNS data marked as public")

        except Exception as e:
            logger.error(f"Error marking data as public: {e}")
            raise

    def get_ingestion_stats(self) -> Dict[str, Any]:
        """Get statistics about ingested BNS data."""
        try:
            # Get collection stats
            collection_query = """
            MATCH (c:Collection {collection_id: $collection_id})
            RETURN c.collection_id as collection_id, c.is_public as is_public
            """
            collection_result = self.graph_service.execute_query(
                collection_query, {"collection_id": self.collection_id}
            )

            # Get chunk stats
            chunk_query = """
            MATCH (ch:Chunk {collection_id: $collection_id})
            RETURN count(ch) as total_chunks,
                   count(DISTINCT ch.chapter_number) as total_chapters,
                   count(DISTINCT ch.section_number) as total_sections
            """
            chunk_result = self.graph_service.execute_query(
                chunk_query, {"collection_id": self.collection_id}
            )

            # Get document stats
            doc_query = """
            MATCH (d:Document {file_id: $file_id})
            RETURN d.file_name as file_name, d.indexed_at as indexed_at
            """
            doc_result = self.graph_service.execute_query(
                doc_query, {"file_id": self.file_id}
            )

            return {
                "collection": collection_result[0] if collection_result else {},
                "chunks": chunk_result[0] if chunk_result else {},
                "document": doc_result[0] if doc_result else {}
            }

        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}

    async def run_ingestion(self, force: bool = False) -> bool:
        """Run the complete BNS ingestion process."""
        print("⚖️  BNS (BHARATIYA NYAYA SANHITA) INGESTION - Neo4j")
        print("=" * 60)
        print(f"Collection ID: {self.collection_id}")
        print(f"File ID: {self.file_id}")
        print(f"User ID: {self.user_id} (public)")
        print()

        try:
            # Load parsed data
            print("📄 Step 1: Loading parsed BNS data...")
            bns_data = self.load_parsed_data()

            # Check existing data
            print("🔍 Step 2: Checking for existing data...")
            exists = self.check_existing_data()

            if exists and not force:
                print("⚠️  BNS data already exists in Neo4j.")
                print("Use --force to re-index")
                return False

            if exists and force:
                print("🗑️  Step 3: Clearing existing data (force mode)...")
                self.clear_existing_data()

            # Generate embeddings
            print("🔗 Step 4: Generating embeddings...")
            chunks = bns_data["chunks"]
            embeddings = self.generate_embeddings(chunks)

            # Prepare chunk objects
            print("📝 Step 5: Preparing chunk objects...")
            chunk_objects = self.prepare_chunk_objects(chunks, embeddings)

            # Index into Neo4j
            print("💾 Step 6: Indexing into Neo4j...")
            success = self.index_bns_data(chunk_objects, embeddings)

            if not success:
                print("❌ INDEXING FAILED!")
                return False

            # Mark as public
            print("🌍 Step 7: Marking as public collection...")
            self.mark_as_public()

            # Get stats
            print("📊 Step 8: Getting ingestion statistics...")
            stats = self.get_ingestion_stats()

            # Print results
            print("\n✅ BNS INGESTION COMPLETED!")
            print("=" * 40)
            print(f"📊 Total Sections: {stats['chunks'].get('total_sections', 0)}")
            print(f"📊 Total Chapters: {stats['chunks'].get('total_chapters', 0)}")
            print(f"📊 Total Chunks: {stats['chunks'].get('total_chunks', 0)}")
            print(f"📊 Collection ID: {stats['collection'].get('collection_id', 'N/A')}")
            print(f"📊 Is Public: {stats['collection'].get('is_public', False)}")
            print(f"📊 Indexed At: {stats['document'].get('indexed_at', 'N/A')}")
            print()
            print("🎯 Next Step: Test legal assistant with BNS queries!")

            return True

        except Exception as e:
            logger.error(f"Ingestion failed: {e}")
            print(f"\n❌ INGESTION FAILED: {e}")
            return False


async def main():
    """Main function to run BNS ingestion."""
    parser = argparse.ArgumentParser(description="Ingest BNS data into Neo4j")
    parser.add_argument("--json-file", default=None,
                       help="Path to parsed BNS JSON file")
    parser.add_argument("--force", action="store_true",
                       help="Force re-indexing even if data exists")

    args = parser.parse_args()

    # Validate configuration
    if not Config.neo4j.PASSWORD:
        print("❌ Error: NEO4J_PASSWORD environment variable not set")
        print("Please configure your Neo4j connection and try again.")
        return False

    runner = BNSIngestionRunner(args.json_file)
    success = await runner.run_ingestion(force=args.force)

    if success:
        print("\n🎉 BNS ingestion completed successfully!")
        print("BNS Act is now available in your legal RAG system.")
    else:
        print("\n💥 BNS ingestion failed.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())