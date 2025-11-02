from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct, Filter, FieldCondition
from typing import List, Dict, Any, Optional
import uuid
import logging
from config import Config

logger = logging.getLogger(__name__)

class QdrantRepository:
    def __init__(self):
        if Config.database.QDRANT_API_KEY:
            url = f"{Config.database.QDRANT_HOST}:{Config.database.QDRANT_PORT}"
            logger.info(f"Initializing Qdrant client with URL: {url}")
            logger.info(f"API Key present: {bool(Config.database.QDRANT_API_KEY)}")
            self.client = QdrantClient(
                url=url,
                api_key=Config.database.QDRANT_API_KEY,
                timeout=Config.database.QDRANT_TIMEOUT
            )
        else:
            logger.info(f"Initializing Qdrant client with host: {Config.database.QDRANT_HOST}:{Config.database.QDRANT_PORT}")
            self.client = QdrantClient(
                host=Config.database.QDRANT_HOST,
                port=Config.database.QDRANT_PORT,
                timeout=Config.database.QDRANT_TIMEOUT
            )

    def collection_exists(self, collection_name: str) -> bool:
        try:
            logger.debug(f"Checking if collection '{collection_name}' exists")
            # Use get_collection instead of collection_exists (which doesn't exist in this version)
            self.client.get_collection(collection_name)
            logger.debug(f"Collection '{collection_name}' exists: True")
            return True
        except Exception as e:
            # Collection doesn't exist if get_collection raises an exception
            logger.debug(f"Collection '{collection_name}' exists: False (exception: {str(e)})")
            return False

    def create_collection(self, collection_name: str) -> bool:
        try:
            if self.collection_exists(collection_name):
                return False

            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=Config.embedding.VECTOR_SIZE,
                    distance=Distance.COSINE
                )
            )
            return True
        except Exception:
            return False

    def delete_collection(self, collection_name: str) -> bool:
        try:
            # Check if collection exists first
            if not self.collection_exists(collection_name):
                return False

            self.client.delete_collection(collection_name)
            return True
        except Exception as e:
            print(f"Error deleting collection '{collection_name}': {str(e)}")
            return False

    def list_collections(self) -> List[str]:
        try:
            logger.debug("Fetching list of collections from Qdrant")
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]
            logger.debug(f"Found {len(collection_names)} collections: {collection_names}")
            return collection_names
        except Exception as e:
            logger.error(f"Failed to list collections: {str(e)}")
            logger.exception("Full exception details:")
            return []


    def link_content(self, collection_name: str, documents: List[Dict[str, Any]]) -> bool:
        try:
            logger.info(f"Linking {len(documents)} documents to collection '{collection_name}'")
            points = []
            for doc in documents:
                text = doc.get("text", "")
                vector = doc.get("vector", [])
                doc_id = doc.get("document_id")

                logger.debug(f"Processing document {doc_id}, text length: {len(text)}, vector length: {len(vector)}")

                point = PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload={
                        "document_id": doc_id,
                        "text": text,
                        "source": doc.get("source", ""),
                        "metadata": doc.get("metadata", {})
                    }
                )
                points.append(point)

            logger.debug(f"Upserting {len(points)} points to collection '{collection_name}'")
            result = self.client.upsert(collection_name=collection_name, points=points)
            logger.info(f"Successfully linked documents to collection '{collection_name}': {result}")
            return True
        except Exception as e:
            logger.error(f"Failed to link content to collection '{collection_name}': {str(e)}")
            logger.exception("Full exception details:")
            return False

    def unlink_content(self, collection_name: str, document_ids: List[str]) -> bool:
        try:
            logger.info(f"Unlinking {len(document_ids)} documents from collection '{collection_name}'")
            for doc_id in document_ids:
                logger.debug(f"Deleting document {doc_id} from collection '{collection_name}'")
                result = self.client.delete(
                    collection_name=collection_name,
                    points_selector=Filter(
                        must=[FieldCondition(key="document_id", match={"value": doc_id})]
                    )
                )
                logger.debug(f"Delete result for {doc_id}: {result}")
            logger.info(f"Successfully unlinked all documents from collection '{collection_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to unlink content from collection '{collection_name}': {str(e)}")
            logger.exception("Full exception details:")
            return False

    def query_collection(self, collection_name: str, query_vector: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        try:
            results = self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit
            )

            return [
                {
                    "id": hit.id,
                    "score": hit.score,
                    "payload": hit.payload
                }
                for hit in results
            ]
        except Exception:
            return []

    def batch_read_files(self, collection_name: str, document_ids: List[str]) -> Dict[str, Any]:
        try:
            logger.debug(f"Checking status of {len(document_ids)} documents in collection '{collection_name}'")
            status = {}
            for doc_id in document_ids:
                logger.debug(f"Checking if document {doc_id} exists in collection '{collection_name}'")
                results = self.client.scroll(
                    collection_name=collection_name,
                    scroll_filter=Filter(
                        must=[FieldCondition(key="document_id", match={"value": doc_id})]
                    ),
                    limit=1
                )
                status[doc_id] = "indexed" if results[0] else "not_found"
                logger.debug(f"Document {doc_id} status: {status[doc_id]}")
            return status
        except Exception as e:
            logger.error(f"Failed to check file status in collection '{collection_name}': {str(e)}")
            logger.exception("Full exception details:")
            return {doc_id: "error" for doc_id in document_ids}