#!/usr/bin/env python3
"""
Simple Constitution Ingestion Script
=====================================
Ingests the simple JSON format from output/constitution/constitution.json
"""

import sys
import json
import re
import asyncio
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.graph_service import get_graph_service
from src.utils.embedding_client import embedding_client


# Article number to Part mapping
ARTICLE_TO_PART = {
    range(1, 5): "I",      # Union and Territory
    range(5, 12): "II",    # Citizenship
    range(12, 36): "III",  # Fundamental Rights
    range(36, 52): "IV",   # Directive Principles
    range(52, 152): "V",   # The Union
    range(152, 238): "VI", # The States
    range(239, 243): "VIII", # Union Territories
    range(243, 244): "IX",  # Panchayats
    range(244, 245): "X",   # Scheduled Areas
    range(245, 264): "XI",  # Union-State Relations
    range(264, 301): "XII", # Finance
    range(301, 308): "XIII", # Trade & Commerce
    range(308, 324): "XIV", # Services
    range(324, 330): "XV",  # Elections
    range(330, 343): "XVI", # Special Provisions
    range(343, 352): "XVII", # Official Language
    range(352, 361): "XVIII", # Emergency
    range(361, 368): "XIX", # Miscellaneous
    range(368, 393): "XX",  # Amendment
}


def get_part_for_article(article_num: int) -> str:
    """Get Part number for an article."""
    for range_obj, part in ARTICLE_TO_PART.items():
        if article_num in range_obj:
            return part
    return "XXII"  # Default for newer articles


def parse_article_entry(entry: Dict[str, str]) -> Dict[str, Any]:
    """Parse a simple article entry into structured format."""
    text = entry.get('Articles', '')

    # Extract article number and title from start
    # Format: "1. Name and territory of the Union\n(1) India..."
    match = re.match(r'^(\d+[A-Z]*)\.\s*([^\n]+?)(?:\n|$)', text)

    if match:
        number = match.group(1)
        title = match.group(2).strip()
    else:
        # Fallback
        number = "0"
        title = text[:50]

    # Get numeric part for Part lookup
    num_only = int(re.match(r'(\d+)', number).group(1)) if re.match(r'(\d+)', number) else 0
    part_number = get_part_for_article(num_only)

    return {
        'id': f"Art-{number}",
        'number': number,
        'title': title,
        'text': text,
        'part_number': part_number,
        'provision_type': 'ARTICLE',
        'references': []
    }


async def run_ingestion():
    """Run the ingestion process."""
    print("🏛️  CONSTITUTION INGESTION (Simple Format)")
    print("=" * 60)

    # Load JSON
    json_path = Path(__file__).parent / "output" / "constitution" / "constitution.json"
    print(f"📄 Loading: {json_path}")

    with open(json_path, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)

    print(f"   ✅ Loaded {len(raw_data)} entries")

    # Parse entries
    articles = [parse_article_entry(entry) for entry in raw_data]
    print(f"   📊 Parsed {len(articles)} articles")

    # Initialize services
    graph_service = get_graph_service()
    graph_service.verify_connection()
    print("   ✅ Neo4j connected")

    # Test embeddings
    test_emb = embedding_client.generate_single_embedding("test")
    print(f"   ✅ Embeddings working (dim={len(test_emb)})")

    # Clean existing data
    print("\n🧹 Cleaning existing Constitution data...")
    cleanup_queries = [
        "MATCH (p:Provision {statute_name: 'Constitution of India'}) DETACH DELETE p",
        "MATCH (s:Statute {name: 'Constitution of India'}) DETACH DELETE s",
        "MATCH (c:Chunk) WHERE c.file_id STARTS WITH 'constitution-' DETACH DELETE c",
        "MATCH (col:Collection {collection_id: 'constitution-golden-source'}) DETACH DELETE col",
    ]
    for q in cleanup_queries:
        graph_service.execute_query(q, {})
    print("   ✅ Cleaned")

    # Create Constitution statute
    print("\n📜 Creating Constitution statute...")
    graph_service.execute_query("""
        MERGE (s:Statute {name: 'Constitution of India'})
        SET s.type = 'CONSTITUTIONAL',
            s.year = 1950,
            s.total_provisions = $total,
            s.indexed_at = datetime()
        RETURN s.name
    """, {"total": len(articles)})
    print("   ✅ Created")

    # Create collection for search
    print("\n📁 Creating search collection...")
    graph_service.execute_query("""
        MERGE (u:User {user_id: 'system'})
        MERGE (col:Collection {collection_id: 'constitution-golden-source'})
        MERGE (u)-[:OWNS]->(col)
    """, {})
    print("   ✅ Created")

    # Process articles in batches
    print("\n📝 Creating Article Provisions...")
    batch_size = 10

    for i in range(0, len(articles), batch_size):
        batch = articles[i:i + batch_size]
        print(f"   🔄 Processing {i+1}-{min(i+batch_size, len(articles))} of {len(articles)}...")

        # Generate embeddings
        texts = [a['text'] for a in batch]
        embeddings = embedding_client.generate_embeddings(texts)

        for article, embedding in zip(batch, embeddings):
            # Create Provision node
            graph_service.execute_query("""
                MATCH (s:Statute {name: 'Constitution of India'})
                MERGE (p:Provision {id: $id})
                SET p.number = $number,
                    p.title = $title,
                    p.text = $text,
                    p.part = $part,
                    p.statute_name = 'Constitution of India',
                    p.provision_type = 'ARTICLE',
                    p.embedding = $embedding,
                    p.indexed_at = datetime()
                MERGE (s)-[:HAS_PROVISION]->(p)
            """, {
                "id": article['id'],
                "number": article['number'],
                "title": article['title'],
                "text": article['text'],
                "part": article['part_number'],
                "embedding": embedding
            })

            # Create Chunk for search (direct Cypher, not using repository)
            chunk_id = f"constitution-{article['id'].lower()}-chunk-001"
            file_id = f"constitution-{article['id'].lower()}"

            graph_service.execute_query("""
                MERGE (u:User {user_id: 'system'})
                MERGE (col:Collection {collection_id: 'constitution-golden-source'})
                MERGE (u)-[:OWNS]->(col)

                MERGE (d:Document {file_id: $file_id})
                SET d.file_name = $file_name,
                    d.source_type = 'constitution',
                    d.indexed_at = datetime()
                MERGE (col)-[:CONTAINS]->(d)

                MERGE (c:Chunk {chunk_id: $chunk_id})
                SET c.text = $text,
                    c.embedding = $embedding,
                    c.file_id = $file_id,
                    c.collection_id = 'constitution-golden-source',
                    c.chunk_type = 'CONCEPT',
                    c.chapter_title = $part,
                    c.section_title = $title,
                    c.indexed_at = datetime()
                MERGE (d)-[:HAS_CHUNK]->(c)
            """, {
                "chunk_id": chunk_id,
                "file_id": file_id,
                "file_name": f"Constitution-{article['id']}",
                "text": article['text'],
                "embedding": embedding,
                "part": article['part_number'],
                "title": article['title']
            })

    print(f"\n✅ SUCCESS! Ingested {len(articles)} articles into Neo4j")
    print("\nVerify with: python debug_neo4j.py")


if __name__ == "__main__":
    asyncio.run(run_ingestion())
