#!/usr/bin/env python3
"""
Debug script to identify why queries aren't working correctly.
This will test each step of the RAG pipeline.
"""

import os
import sys
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

load_dotenv()

from repositories.neo4j_repository import neo4j_repository
from services.query_service import QueryService
from utils.embedding_client import embedding_client
from config import Config

def test_neo4j_connection():
    """Test basic Neo4j connection"""
    print("🔍 Testing Neo4j connection...")
    try:
        from services.graph_service import graph_service
        result = graph_service.execute_query("RETURN 1 as test")
        print("✅ Neo4j connection successful")
        return True
    except Exception as e:
        print(f"❌ Neo4j connection failed: {e}")
        return False

def test_chunks_exist():
    """Test if any chunks exist in the database"""
    print("\n🔍 Checking if chunks exist...")
    try:
        from services.graph_service import graph_service
        result = graph_service.execute_query("""
            MATCH (c:Chunk)
            RETURN count(c) as total_chunks,
                   collect(DISTINCT c.file_id)[0..5] as sample_file_ids,
                   collect(DISTINCT c.collection_id)[0..5] as sample_collection_ids
        """)

        if result and len(result) > 0:
            record = result[0]
            total = record['total_chunks']
            file_ids = record['sample_file_ids']
            collection_ids = record['sample_collection_ids']

            print(f"✅ Found {total} chunks in database")
            print(f"📁 Sample file IDs: {file_ids}")
            print(f"📂 Sample collection IDs: {collection_ids}")
            return total > 0, file_ids, collection_ids
        else:
            print("❌ No chunks found in database")
            return False, [], []
    except Exception as e:
        print(f"❌ Error checking chunks: {e}")
        return False, [], []

def test_vector_index():
    """Test if vector index exists and works"""
    print("\n🔍 Testing vector index...")
    try:
        from services.graph_service import graph_service

        # Check if index exists
        result = graph_service.execute_query("""
            SHOW INDEXES
            YIELD name, type, labelsOrTypes, properties
            WHERE type = 'VECTOR'
            RETURN name, labelsOrTypes, properties
        """)

        if result:
            print("✅ Vector indexes found:")
            for record in result:
                print(f"   - {record['name']}: {record['labelsOrTypes']} -> {record['properties']}")
            return True
        else:
            print("❌ No vector indexes found")
            return False
    except Exception as e:
        print(f"❌ Error checking vector index: {e}")
        return False

def test_embeddings():
    """Test embedding generation"""
    print("\n🔍 Testing embedding generation...")
    try:
        test_query = "What is the law about contracts?"
        embedding = embedding_client.generate_single_embedding(test_query)
        print(f"✅ Generated embedding with {len(embedding)} dimensions")
        print(f"📊 Sample values: {embedding[:5]}...")
        return embedding
    except Exception as e:
        print(f"❌ Error generating embedding: {e}")
        return None

def test_vector_search(embedding, file_ids):
    """Test vector search directly"""
    print("\n🔍 Testing vector search...")
    try:
        # Test with different parameters
        test_cases = [
            {"collection_ids": None, "file_ids": None, "desc": "All collections"},
            {"collection_ids": None, "file_ids": file_ids[:1] if file_ids else None, "desc": f"Specific file: {file_ids[0] if file_ids else 'None'}"},
        ]

        for test_case in test_cases:
            print(f"   Testing: {test_case['desc']}")

            results = neo4j_repository.vector_search(
                query_embedding=embedding,
                collection_ids=test_case["collection_ids"],
                file_ids=test_case["file_ids"],
                top_k=10
            )

            print(f"   📊 Found {len(results)} results")

            if results:
                print("   ✅ Sample result:")
                result = results[0]
                print(f"      - Chunk ID: {result.get('chunk_id', 'N/A')}")
                print(f"      - Score: {result.get('score', 'N/A')}")
                print(f"      - Text preview: {result.get('text', '')[:100]}...")
                print(f"      - File ID: {result.get('file_id', 'N/A')}")

                # Check relevance threshold
                max_score = max(r.get('score', 0) for r in results)
                threshold = Config.query.RELEVANCE_THRESHOLD
                print(f"   📈 Max score: {max_score}, Threshold: {threshold}")

                if max_score < threshold:
                    print(f"   ⚠️  WARNING: Best score ({max_score}) below threshold ({threshold})")
                    print(f"      This means results will be filtered out!")

            print()

        return len(results) > 0
    except Exception as e:
        print(f"❌ Error in vector search: {e}")
        return False

def test_full_query():
    """Test full query pipeline"""
    print("\n🔍 Testing full query pipeline...")
    try:
        query_service = QueryService()
        test_query = "What is the law about contracts?"

        print(f"Query: {test_query}")

        response = query_service.search(
            collection_name="test",
            query_text=test_query,
            limit=5
        )

        print(f"✅ Query completed")
        print(f"📝 Answer: {response.answer[:200]}...")
        print(f"🎯 Confidence: {response.confidence}")
        print(f"📚 Found {len(response.chunks)} chunks")

        if response.chunks:
            for i, chunk in enumerate(response.chunks[:2]):
                print(f"   Chunk {i+1}: Score={chunk.relevance_score}, Text={chunk.text[:50]}...")

        return response.answer != "Context not found"

    except Exception as e:
        print(f"❌ Error in full query: {e}")
        return False

def main():
    print("=" * 80)
    print("🔧 RAG QUERY DEBUG TOOL")
    print("=" * 80)
    print(f"🔧 Relevance Threshold: {Config.query.RELEVANCE_THRESHOLD}")
    print(f"🔧 Vector Index Name: {Config.neo4j.VECTOR_INDEX_NAME}")
    print(f"🔧 Embedding Provider: {Config.embedding.PROVIDER}")
    print(f"🔧 Embedding Model: {Config.embedding.MODEL_NAME}")
    print("=" * 80)

    # Test each component
    if not test_neo4j_connection():
        print("\n❌ Cannot proceed without Neo4j connection")
        return

    has_chunks, file_ids, collection_ids = test_chunks_exist()
    if not has_chunks:
        print("\n❌ No chunks found - you need to index some documents first!")
        print("💡 Try uploading documents via the /api/v1/link-content endpoint")
        return

    if not test_vector_index():
        print("\n❌ Vector index issues detected")
        return

    embedding = test_embeddings()
    if not embedding:
        print("\n❌ Cannot generate embeddings")
        return

    if not test_vector_search(embedding, file_ids):
        print("\n❌ Vector search not working")
        return

    if test_full_query():
        print("\n✅ Full query pipeline working!")
    else:
        print("\n❌ Full query pipeline failed")

    print("\n" + "=" * 80)
    print("🎯 DEBUG COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()