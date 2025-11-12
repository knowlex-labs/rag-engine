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
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]
            exists = collection_name in collection_names
            logger.debug(f"Collection '{collection_name}' exists: {exists}")
            return exists
        except Exception as e:
            logger.error(f"Error checking if collection '{collection_name}' exists: {str(e)}")
            return False

    def ensure_indexes(self, collection_name: str) -> bool:
        try:
            logger.info(f"Ensuring payload indexes exist on collection '{collection_name}'")
            try:
                self.client.create_payload_index(
                    collection_name=collection_name,
                    field_name="document_id",
                    field_schema="keyword"
                )
                logger.debug(f"Created index for document_id on collection '{collection_name}'")
            except Exception as e:
                if "already exists" in str(e).lower():
                    logger.debug(f"Index for document_id already exists on collection '{collection_name}'")
                else:
                    logger.warning(f"Could not create index for document_id: {str(e)}")

            try:
                self.client.create_payload_index(
                    collection_name=collection_name,
                    field_name="metadata.chunk_type",
                    field_schema="keyword"
                )
                logger.debug(f"Created index for metadata.chunk_type on collection '{collection_name}'")
            except Exception as e:
                if "already exists" in str(e).lower():
                    logger.debug(f"Index for metadata.chunk_type already exists on collection '{collection_name}'")
                else:
                    logger.warning(f"Could not create index for metadata.chunk_type: {str(e)}")

            logger.info(f"Payload indexes ensured on collection '{collection_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to ensure indexes on collection '{collection_name}': {str(e)}")
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

            self.ensure_indexes(collection_name)
            logger.info(f"Created collection '{collection_name}' with payload indexes")
            return True
        except Exception as e:
            logger.error(f"Failed to create collection '{collection_name}': {str(e)}")
            return False

    def delete_collection(self, collection_name: str) -> bool:
        try:
            if not self.collection_exists(collection_name):
                return False

            self.client.delete_collection(collection_name)
            return True
        except Exception as e:
            print(f"Error deleting collection '{collection_name}': {str(e)}")
            return False

    def list_collections(self) -> List[str]:
        try:
            logger.info("Fetching list of collections from Qdrant")
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
                chunk_id = doc.get("chunk_id")

                logger.debug(f"Processing document {doc_id}, chunk_id: {chunk_id}, text length: {len(text)}, vector length: {len(vector)}")

                payload = {
                    "document_id": doc_id,
                    "text": text,
                    "source": doc.get("source", ""),
                    "metadata": doc.get("metadata", {})
                }

                if chunk_id:
                    payload["chunk_id"] = chunk_id

                point = PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload=payload
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

    def query_collection(self, collection_name: str, query_vector: List[float], limit: int = 5, chunk_type: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            query_filter = None
            if chunk_type:
                query_filter = Filter(
                    must=[FieldCondition(key="metadata.chunk_type", match={"value": chunk_type})]
                )

            results = self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit,
                query_filter=query_filter
            )

            return [
                {
                    "id": hit.id,
                    "score": hit.score,
                    "payload": hit.payload
                }
                for hit in results
            ]
        except Exception as e:
            error_msg = str(e)
            if "Index required" in error_msg and "metadata.chunk_type" in error_msg:
                logger.warning(f"Missing index detected for collection '{collection_name}', attempting to create indexes")
                if self.ensure_indexes(collection_name):
                    logger.info(f"Indexes created, retrying query for collection '{collection_name}'")
                    try:
                        results = self.client.search(
                            collection_name=collection_name,
                            query_vector=query_vector,
                            limit=limit,
                            query_filter=query_filter
                        )
                        return [
                            {
                                "id": hit.id,
                                "score": hit.score,
                                "payload": hit.payload
                            }
                            for hit in results
                        ]
                    except Exception as retry_error:
                        logger.error(f"Error querying collection after creating indexes: {retry_error}")
                        return []

            logger.error(f"Error querying collection: {e}")
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
            error_msg = str(e)
            if "Index required" in error_msg and "document_id" in error_msg:
                logger.warning(f"Missing index detected for collection '{collection_name}', attempting to create indexes")
                if self.ensure_indexes(collection_name):
                    logger.info(f"Indexes created, retrying batch_read_files for collection '{collection_name}'")
                    try:
                        status = {}
                        for doc_id in document_ids:
                            results = self.client.scroll(
                                collection_name=collection_name,
                                scroll_filter=Filter(
                                    must=[FieldCondition(key="document_id", match={"value": doc_id})]
                                ),
                                limit=1
                            )
                            status[doc_id] = "indexed" if results[0] else "not_found"
                        return status
                    except Exception as retry_error:
                        logger.error(f"Error checking file status after creating indexes: {retry_error}")
                        return {doc_id: "error" for doc_id in document_ids}

            logger.error(f"Failed to check file status in collection '{collection_name}': {str(e)}")
            logger.exception("Full exception details:")
            return {doc_id: "error" for doc_id in document_ids}