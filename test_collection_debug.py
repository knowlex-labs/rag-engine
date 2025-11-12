#!/usr/bin/env python3
"""Debug script to test collection name handling"""

import sys
import os

# Add src directory to path (works cross-platform)
script_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(script_dir, 'src')
sys.path.insert(0, src_dir)

from repositories.qdrant_repository import QdrantRepository
import logging

logging.basicConfig(level=logging.DEBUG)

def test_collection():
    repo = QdrantRepository()

    collection_name = "Law's of Motion"

    print(f"\n=== Testing collection: {collection_name} ===")
    print(f"Collection name repr: {repr(collection_name)}")
    print(f"Collection name encoded: {collection_name.encode('utf-8')}")

    # List all collections
    print("\n=== Listing all collections ===")
    collections = repo.list_collections()
    print(f"Found {len(collections)} collections:")
    for col in collections:
        print(f"  - {col!r}")

    # Check if our collection exists
    print(f"\n=== Checking if '{collection_name}' exists ===")
    exists = repo.collection_exists(collection_name)
    print(f"Collection exists: {exists}")

    # Try creating it if it doesn't exist
    if not exists:
        print(f"\n=== Creating collection '{collection_name}' ===")
        created = repo.create_collection(collection_name)
        print(f"Collection created: {created}")

        # Check again
        exists_after = repo.collection_exists(collection_name)
        print(f"Collection exists after creation: {exists_after}")

if __name__ == "__main__":
    test_collection()
