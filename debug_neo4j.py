#!/usr/bin/env python3
"""
Debug Neo4j Database State
"""

import os
from dotenv import load_dotenv
from neo4j import GraphDatabase
import logging

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_database():
    print("🔍 DEBUGGING NEO4J DATABASE STATE")
    print("=" * 50)

    # Connect to Neo4j
    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
    )

    with driver.session() as session:
        print(f"Connected to: {os.getenv('NEO4J_URI')}")
        print(f"Username: {os.getenv('NEO4J_USERNAME')}")

        # Check database info
        print("\n📊 DATABASE INFO:")
        result = session.run("CALL dbms.components() YIELD name, versions")
        for record in result:
            print(f"  {record['name']}: {record['versions']}")

        # Count all nodes
        print("\n📈 NODE COUNTS:")
        labels = ["User", "Collection", "Document", "Chunk", "Entity"]
        for label in labels:
            result = session.run(f"MATCH (n:{label}) RETURN count(n) as count")
            count = result.single()['count']
            print(f"  {label}: {count}")

        # Count all relationships
        print("\n🔗 RELATIONSHIP COUNTS:")
        result = session.run("MATCH ()-[r]->() RETURN type(r) as rel_type, count(r) as count")
        for record in result:
            print(f"  {record['rel_type']}: {record['count']}")

        # Show recent chunks if any exist
        print("\n📄 RECENT CHUNKS (if any):")
        result = session.run("MATCH (c:Chunk) RETURN c.chunk_id, c.file_id, c.collection_id, substring(c.text, 0, 100) as preview, size(c.embedding) as embedding_size LIMIT 5")
        chunks = list(result)
        if chunks:
            for record in chunks:
                print(f"  Chunk ID: {record.get('c.chunk_id', 'N/A')}")
                print(f"  File ID: {record.get('c.file_id', 'N/A')}")
                print(f"  Collection ID: {record.get('c.collection_id', 'N/A')}")
                print(f"  Embedding size: {record.get('embedding_size', 'N/A')}")
                print(f"  Preview: {record.get('preview', 'N/A')}...")
                print("  ---")
        else:
            print("  ❌ No chunks found")

        # Show indexes and constraints
        print("\n🏗️ INDEXES:")
        result = session.run("SHOW INDEXES YIELD name, type, state")
        for record in result:
            print(f"  {record['name']}: {record['type']} ({record['state']})")

        print("\n🔒 CONSTRAINTS:")
        result = session.run("SHOW CONSTRAINTS YIELD name, type")
        for record in result:
            print(f"  {record['name']}: {record['type']}")

    driver.close()
    print("\n✅ Debug complete!")

if __name__ == "__main__":
    debug_database()