
import requests
import os
import tempfile
from typing import List, Optional
import logging
import asyncio

from repositories.neo4j_repository import neo4j_repository
from services.storage.gcs_storage_service import GCSStorageService
from services.hierarchical_chunking_service import chunking_service
from utils.embedding_client import embedding_client
from models.api_models import BatchLinkRequest, LinkItem, IndexingStatus
from parsers.parser_factory import ParserFactory
from config import Config

logger = logging.getLogger(__name__)

class CollectionService:
    def __init__(self):
        self.neo4j_repo = neo4j_repository
        self.embedding_client = embedding_client
        self.storage_service = GCSStorageService()

    def _get_user_collection(self, user_id: str) -> str:
        return f"user_{user_id}"

    async def process_batch(self, request: BatchLinkRequest, tenant_id: str):
        collection_id = request.items[0].collection_id if request.items else "default"
        logger.info(f"Starting batch process for tenant {tenant_id}, collection {collection_id}")
        self.neo4j_repo.create_user_collection(tenant_id, collection_id)

        results = []
        for item in request.items:
            try:
                logger.info(f"Processing item {item.file_id} (type: {item.type})")
                source = self._resolve_source(item)
                logger.info(f"Parsing content for {item.file_id}")
                parsed = self._parse_content(source, item.type)
                logger.info(f"Chunking content for {item.file_id}")
                chunks = self._chunk_content(parsed, item.type)
                logger.info(f"Generating embeddings for {len(chunks)} chunks of {item.file_id}")
                embeddings = self._generate_embeddings(chunks)

                logger.info(f"Indexing chunks to Neo4j for {item.file_id}")
                self.neo4j_repo.index_chunks(
                    chunks=chunks,
                    embeddings=embeddings,
                    user_id=tenant_id,
                    collection_id=item.collection_id or "default",
                    file_id=item.file_id,
                    file_name=parsed.metadata.title or item.title or "Unknown",
                    source_type=item.type
                )
                logger.info(f"Successfully processed {item.file_id}")

                results.append({
                    "file_id": item.file_id,
                    "status": "INDEXING_SUCCESS",
                    "error": None
                })

            except Exception as e:
                logger.error(f"Failed to process {item.file_id}: {e}")
                results.append({
                    "file_id": item.file_id,
                    "status": "INDEXING_FAILED",
                    "error": str(e)
                })

        return results

    def _resolve_source(self, item: LinkItem) -> str:
        from urllib.parse import unquote
        if item.type == 'file':
            if not item.gcs_url:
                raise ValueError("Missing gcs_url")
            
            # Unquote in case of %20 etc
            gcs_url = unquote(item.gcs_url)
            
            # If it's a GCS HTTPS URL for our bucket, use native GCS client
            bucket_prefix = f'https://storage.googleapis.com/{Config.gcs.BUCKET_NAME}/'
            if gcs_url.startswith(bucket_prefix):
                storage_path = gcs_url[len(bucket_prefix):]
                return self.storage_service.download_for_processing(storage_path)
            
            if gcs_url.startswith(('http://', 'https://')):
                return self._download_from_url(gcs_url)
                
            return self._download_from_gcs(gcs_url)
        return item.url

    def _download_from_url(self, url: str) -> str:
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            # Extract filename from URL or header if possible, else default
            # Simple approach: temp file with generic suffix or try to guess from Content-Disposition
            # For now, we'll just fetch and assume pdf/text based on subsequent parser logic or just use a safe suffix
            suffix = ".pdf" # Defaulting for now, parser might auto-detect or fail if mismatch. 
            # ideally item.type='file' is vague. But parsing logic usually handles magic numbers or just needs bytes.
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                for chunk in response.iter_content(chunk_size=8192):
                    tmp_file.write(chunk)
                return tmp_file.name
        except Exception as e:
            logger.error(f"Failed to download file from URL {url}: {e}")
            raise ValueError(f"Failed to download file: {str(e)}")

    def _download_from_gcs(self, gcs_path: str) -> str:
        from urllib.parse import unquote
        gcs_path = unquote(gcs_path)
        if gcs_path.startswith("gs://"):
            parts = gcs_path.replace("gs://", "").split("/", 1)
            if len(parts) > 1:
                return self.storage_service.download_for_processing(parts[1])
        raise ValueError(f"Invalid GCS URL: {gcs_path}")

    def _parse_content(self, source: str, item_type: str):
        parser = ParserFactory.get_parser(item_type)
        return parser.parse(source)

    def _chunk_content(self, parsed_content, item_type: str):
        return chunking_service.chunk_parsed_content(parsed_content, item_type)

    def _generate_embeddings(self, chunks):
        texts = [chunk.text for chunk in chunks]
        return self.embedding_client.generate_embeddings(texts)

    def _set_status(self, tenant_id: str, file_id: str, status: IndexingStatus, error: Optional[str] = None, item_name: Optional[str] = None, source_type: Optional[str] = None):
        logger.info(f"Status tracking not yet implemented for Neo4j: file_id={file_id}, status={status.value}")

    def get_status(self, tenant_id: str, file_id: str) -> dict:
        return {"status": "UNKNOWN", "file_id": file_id, "message": "Status tracking not yet implemented for Neo4j"}



    def unlink_content(self, collection_name: Optional[str], file_ids: List[str], user_id: str) -> int:
        deleted_count = 0
        for file_id in file_ids:
            try:
                success = self.neo4j_repo.delete_file(user_id, file_id)
                if success:
                    deleted_count += 1
            except Exception:
                logger.error(f"Error unlinking file {file_id}", exc_info=True)
        return deleted_count

    def delete_collection(self, user_id: str, collection_id: str) -> bool:
        return self.neo4j_repo.delete_collection(user_id, collection_id)

    def purge_user_data(self, user_id: str) -> bool:
        logger.warning(f"Purge user data not implemented for Neo4j: user_id={user_id}")
        return False
