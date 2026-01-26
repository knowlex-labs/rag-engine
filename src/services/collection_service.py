
import requests
import os
import tempfile
from typing import List, Optional
import logging
import asyncio

from repositories.neo4j_repository import neo4j_repository
from services.storage.storage_factory import get_storage_service
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
        self.storage_service = get_storage_service()

    def _get_user_collection(self, user_id: str) -> str:
        return f"user_{user_id}"

    async def process_batch(self, request: BatchLinkRequest, tenant_id: str):
        collection_id = request.items[0].collection_id if request.items else "default"
        # Get content_type from first item (all items in batch should have same content_type)
        content_type = request.items[0].content_type.value if request.items and request.items[0].content_type else "legal"
        logger.info(f"Starting batch process for tenant {tenant_id}, collection {collection_id}, content_type {content_type}")
        self.neo4j_repo.create_user_collection(tenant_id, collection_id, content_type)

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

                # Prepare news metadata if content_type is news
                news_metadata = None
                item_content_type = item.content_type.value if item.content_type else "legal"
                if item_content_type == "news":
                    # Extract news metadata from parsed content or item attributes
                    news_metadata = self._extract_news_metadata(parsed, item)

                logger.info(f"Indexing chunks to Neo4j for {item.file_id}")
                self.neo4j_repo.index_chunks(
                    chunks=chunks,
                    embeddings=embeddings,
                    user_id=tenant_id,
                    collection_id=item.collection_id or "default",
                    file_id=item.file_id,
                    file_name=parsed.metadata.title or item.title or "Unknown",
                    source_type=item.type,
                    content_type=item_content_type,
                    news_metadata=news_metadata
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
            if not item.storage_url:
                raise ValueError("Missing storage_url")

            # Unquote in case of %20 etc
            storage_url = unquote(item.storage_url)
            logger.info(f"Resolving storage URL: {storage_url}")

            # Handle local:// URLs (local storage)
            if storage_url.startswith('local://'):
                logger.info(f"Downloading from local storage: {storage_url}")
                local_path = self.storage_service.download_for_processing(storage_url)
                if not local_path:
                    raise ValueError(f"Failed to get file from local storage: {storage_url}")
                logger.info(f"Local path: {local_path}")
                return local_path

            # Handle HTTP/HTTPS URLs
            if storage_url.startswith(('http://', 'https://')):
                logger.info(f"Downloading from HTTP URL: {storage_url}")
                return self._download_from_url(storage_url)

            raise ValueError(f"Unsupported storage URL format: {storage_url}")
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


    def _parse_content(self, source: str, item_type: str):
        parser = ParserFactory.get_parser(item_type)
        return parser.parse(source)

    def _chunk_content(self, parsed_content, item_type: str):
        return chunking_service.chunk_parsed_content(parsed_content, item_type)

    def _generate_embeddings(self, chunks):
        texts = [chunk.text for chunk in chunks]
        return self.embedding_client.generate_embeddings(texts)

    def _extract_news_metadata(self, parsed_content, item: LinkItem) -> dict:
        """Extract news-specific metadata from parsed content and LinkItem"""
        from datetime import datetime

        metadata = {}

        # Extract from parsed content metadata
        if hasattr(parsed_content, 'metadata') and parsed_content.metadata:
            # Try to extract publication date from metadata
            if hasattr(parsed_content.metadata, 'publish_date'):
                metadata['published_date'] = parsed_content.metadata.publish_date

            # Extract author if available
            if hasattr(parsed_content.metadata, 'author'):
                metadata['author'] = parsed_content.metadata.author

            # Extract headline (title)
            if hasattr(parsed_content.metadata, 'title'):
                metadata['headline'] = parsed_content.metadata.title

        # Extract from URL if it's a web source
        if item.url:
            metadata['source_url'] = item.url
            # Try to extract source name from URL domain
            try:
                from urllib.parse import urlparse
                parsed_url = urlparse(item.url)
                metadata['source_name'] = parsed_url.netloc
            except:
                pass

        # Add crawled timestamp
        metadata['crawled_date'] = datetime.now().isoformat()

        # For now, these would need to be provided via API or extracted using NLP
        # metadata['news_category'] = "general"
        # metadata['news_subcategory'] = None
        # metadata['tags'] = []
        # metadata['summary'] = None

        return metadata if metadata else None

    def _set_status(self, tenant_id: str, file_id: str, status: IndexingStatus, error: Optional[str] = None, item_name: Optional[str] = None, source_type: Optional[str] = None):
        logger.info(f"Status tracking not yet implemented for Neo4j: file_id={file_id}, status={status.value}")

    def get_status(self, tenant_id: str, file_id: str) -> dict:
        """Check if a document is indexed in Neo4j."""
        try:
            query = "MATCH (d:Document {file_id: $file_id}) RETURN d.indexed_at as indexed_at"
            result = self.neo4j_repo.graph_service.execute_query(query, {"file_id": file_id})
            
            if result:
                return {
                    "status": "READY", 
                    "file_id": file_id, 
                    "message": "Document is indexed and ready for AI",
                    "indexed_at": result[0]["indexed_at"]
                }
            return {
                "status": "PROCESSING", 
                "file_id": file_id, 
                "message": "Document is being processed or not found"
            }
        except Exception as e:
            logger.error(f"Error checking status: {e}")
            return {"status": "ERROR", "file_id": file_id, "message": str(e)}



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
