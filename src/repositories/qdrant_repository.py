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

            indexes_to_create = [
                ("document_id", "keyword"),
                ("metadata.chunk_type", "keyword"),
                ("metadata.chapter_num", "integer"),
                ("metadata.content_type", "keyword"),
                ("metadata.book_metadata.book_id", "keyword"),
                ("metadata.book_metadata.book_title", "keyword"),
            ]

            for field_name, field_schema in indexes_to_create:
                self._create_single_index(collection_name, field_name, field_schema)

            logger.info(f"Payload indexes ensured on collection '{collection_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to ensure indexes on collection '{collection_name}': {str(e)}")
            return False

    def _create_single_index(self, collection_name: str, field_name: str, field_schema: str) -> None:
        try:
            self.client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=field_schema
            )
            logger.debug(f"Created index for {field_name} on collection '{collection_name}'")
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.debug(f"Index for {field_name} already exists on collection '{collection_name}'")
            else:
                logger.warning(f"Could not create index for {field_name}: {str(e)}")

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

            points = [self._create_point_from_document(doc) for doc in documents]
            self._upload_points_in_batches(collection_name, points)

            logger.info(f"Successfully linked all {len(documents)} documents to collection '{collection_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to link content to collection '{collection_name}': {str(e)}")
            logger.exception("Full exception details:")
            return False

    def _create_point_from_document(self, doc: Dict[str, Any]) -> PointStruct:
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

        return PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload=payload
        )

    def _upload_points_in_batches(self, collection_name: str, points: List[PointStruct], batch_size: int = 500) -> None:
        total_batches = (len(points) + batch_size - 1) // batch_size
        logger.info(f"Uploading {len(points)} points in {total_batches} batches (batch size: {batch_size})")

        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            logger.info(f"Uploading batch {batch_num}/{total_batches} ({len(batch)} points)...")
            result = self.client.upsert(collection_name=collection_name, points=batch)
            logger.debug(f"Batch {batch_num} upload result: {result}")

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

            results = self._search_with_retry(collection_name, query_vector, limit, query_filter)
            return self._format_search_results(results)
        except Exception as e:
            logger.error(f"Error querying collection: {e}")
            return []

    def _search_with_retry(self, collection_name: str, query_vector: List[float], limit: int, query_filter: Optional[Filter]) -> List[Any]:
        try:
            return self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit,
                query_filter=query_filter
            )
        except Exception as e:
            if "Index required" in str(e):
                logger.warning(f"Missing index detected for collection '{collection_name}', attempting to create indexes")
                if self.ensure_indexes(collection_name):
                    logger.info(f"Indexes created, retrying query for collection '{collection_name}'")
                    return self.client.search(
                        collection_name=collection_name,
                        query_vector=query_vector,
                        limit=limit,
                        query_filter=query_filter
                    )
            raise

    def _format_search_results(self, results: List[Any]) -> List[Dict[str, Any]]:
        return [
            {
                "id": hit.id,
                "score": hit.score,
                "payload": hit.payload
            }
            for hit in results
        ]

    def get_all_embeddings(self, collection_name: str, limit: int = 100, offset: Optional[str] = None, include_vectors: bool = False) -> Dict[str, Any]:
        try:
            logger.info(f"Retrieving embeddings from collection '{collection_name}' with limit={limit}, include_vectors={include_vectors}")

            collection_info = self.client.get_collection(collection_name)
            total_count = collection_info.points_count

            result = self.client.scroll(
                collection_name=collection_name,
                limit=limit,
                offset=offset,
                with_vectors=include_vectors,
                with_payload=True
            )

            points, next_offset = result
            embeddings = self._format_embeddings(points, include_vectors)

            logger.info(f"Retrieved {len(embeddings)} embeddings from collection '{collection_name}'")

            return {
                "embeddings": embeddings,
                "next_offset": next_offset,
                "total_count": total_count,
                "has_more": next_offset is not None,
                "collection_info": {
                    "name": collection_name,
                    "points_count": total_count,
                    "vectors_count": collection_info.vectors_count if hasattr(collection_info, 'vectors_count') else total_count
                }
            }

        except Exception as e:
            logger.error(f"Failed to retrieve embeddings from collection '{collection_name}': {str(e)}")
            logger.exception("Full exception details:")
            return {
                "embeddings": [],
                "next_offset": None,
                "total_count": 0,
                "has_more": False,
                "collection_info": {},
                "error": str(e)
            }

    def _format_embeddings(self, points: List[Any], include_vectors: bool) -> List[Dict[str, Any]]:
        embeddings = []
        for point in points:
            embedding_item = {
                "id": point.id,
                "document_id": point.payload.get("document_id", ""),
                "text": point.payload.get("text", ""),
                "source": point.payload.get("source", ""),
                "metadata": point.payload.get("metadata", {})
            }

            if include_vectors and point.vector:
                embedding_item["vector"] = point.vector

            embeddings.append(embedding_item)
        return embeddings

    def batch_read_files(self, collection_name: str, document_ids: List[str]) -> Dict[str, Any]:
        try:
            logger.debug(f"Checking status of {len(document_ids)} documents in collection '{collection_name}'")
            return self._check_documents_status(collection_name, document_ids)
        except Exception as e:
            if "Index required" in str(e):
                logger.warning(f"Missing index detected for collection '{collection_name}', attempting to create indexes")
                if self.ensure_indexes(collection_name):
                    logger.info(f"Indexes created, retrying batch_read_files for collection '{collection_name}'")
                    try:
                        return self._check_documents_status(collection_name, document_ids)
                    except Exception as retry_error:
                        logger.error(f"Error checking file status after creating indexes: {retry_error}")
                        return {doc_id: "error" for doc_id in document_ids}

            logger.error(f"Failed to check file status in collection '{collection_name}': {str(e)}")
            logger.exception("Full exception details:")
            return {doc_id: "error" for doc_id in document_ids}

    def _check_documents_status(self, collection_name: str, document_ids: List[str]) -> Dict[str, str]:
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