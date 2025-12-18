import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, '/Users/nakuljn/Documents/Github/parkho-labs/services/rag-engine/src')

load_dotenv()

from services.graph_service import graph_service

USER_ID = "5vHWKkjvzNYUImkiRKFoinsDDFS2"
FILE_ID = "5278f040-a939-4955-a6ef-2283f11d3f00"

def run_query(title, query, params=None):
    print("\n" + "=" * 80)
    print(f"QUERY: {title}")
    print("=" * 80)
    print(f"Cypher: {query}")
    if params:
        print(f"Params: {params}")

    try:
        results = graph_service.execute_query(query, params or {})
        print(f"\nResults ({len(results)} records):")

        if not results:
            print("No results found.")
            return

        for i, record in enumerate(results[:10], 1):
            print(f"\n--- Record {i} ---")
            for key in record.keys():
                value = record[key]
                if isinstance(value, str) and len(value) > 200:
                    print(f"{key}: {value[:200]}...")
                elif key == 'embedding':
                    print(f"{key}: [vector of {len(value)} dimensions]")
                else:
                    print(f"{key}: {value}")

        if len(results) > 10:
            print(f"\n... and {len(results) - 10} more records")

    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    print("=" * 80)
    print("NEO4J GRAPH INSPECTION")
    print("=" * 80)

    # Check connection
    print("\nTesting Neo4j connection...")
    try:
        graph_service.execute_query("RETURN 1 as test")
        print("✅ Connected to Neo4j")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return

    # Query 1: Count nodes
    run_query(
        "Count all nodes by label",
        """
        MATCH (n)
        RETURN labels(n) as label, count(n) as count
        ORDER BY count DESC
        """
    )

    # Query 2: Check user structure
    run_query(
        "User collection structure",
        """
        MATCH (u:User {user_id: $user_id})-[:OWNS]->(col:Collection)
        RETURN u.user_id, col.collection_id
        """,
        {"user_id": USER_ID}
    )

    # Query 3: Document and chunks
    run_query(
        "Documents and chunk counts",
        """
        MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)
        RETURN d.file_id, d.file_name, d.source_type, count(c) as chunk_count
        ORDER BY chunk_count DESC
        """
    )

    # Query 4: Sample chunks
    run_query(
        "Sample chunks from your document",
        """
        MATCH (c:Chunk {file_id: $file_id})
        RETURN c.chunk_id, c.chunk_type, c.page_start, c.page_end,
               substring(c.text, 0, 150) as text_preview,
               size(c.embedding) as embedding_dim,
               c.key_terms
        LIMIT 5
        """,
        {"file_id": FILE_ID}
    )

    # Query 5: Chunk types distribution
    run_query(
        "Chunk types distribution",
        """
        MATCH (c:Chunk {file_id: $file_id})
        RETURN c.chunk_type, count(c) as count
        ORDER BY count DESC
        """,
        {"file_id": FILE_ID}
    )

    # Query 6: Check for legal entities
    run_query(
        "Legal entities (if any)",
        """
        MATCH (c:Chunk {file_id: $file_id})-[r:MENTIONS]->(e)
        RETURN labels(e) as entity_type, count(e) as count
        """,
        {"file_id": FILE_ID}
    )

    # Query 7: Vector index info
    run_query(
        "Vector index information",
        """
        SHOW INDEXES
        YIELD name, type, labelsOrTypes, properties, options
        WHERE type = 'VECTOR'
        RETURN name, labelsOrTypes, properties, options
        """
    )

    # Query 8: Full graph path
    run_query(
        "Full graph path for your document",
        """
        MATCH path = (u:User {user_id: $user_id})-[:OWNS]->(col:Collection)-[:CONTAINS]->
                     (d:Document {file_id: $file_id})-[:HAS_CHUNK]->(c:Chunk)
        RETURN u.user_id, col.collection_id, d.file_name,
               count(c) as total_chunks,
               collect(c.chunk_type)[0..5] as sample_chunk_types
        """,
        {"user_id": USER_ID, "file_id": FILE_ID}
    )

    print("\n" + "=" * 80)
    print("INSPECTION COMPLETE")
    print("=" * 80)
    print("\nTo visualize the graph in Neo4j Browser:")
    print("1. Open: https://15980118.databases.neo4j.io/browser/")
    print("2. Login with your credentials")
    print("3. Run this query to see the full graph:\n")
    print(f"""
MATCH path = (u:User {{user_id: '{USER_ID}'}})-[:OWNS]->(col:Collection)
             -[:CONTAINS]->(d:Document {{file_id: '{FILE_ID}'}})
             -[:HAS_CHUNK]->(c:Chunk)
RETURN path LIMIT 25
    """)

if __name__ == "__main__":
    main()
