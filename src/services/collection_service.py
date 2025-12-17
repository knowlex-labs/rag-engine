
import requests
import os
import tempfile
from typing import List, Optional
import logging
import asyncio
import uuid
from datetime import datetime

from repositories.qdrant_repository import QdrantRepository
from services.storage.gcs_storage_service import GCSStorageService
from services.hierarchical_chunking_service import chunking_service
from utils.embedding_client import embedding_client
from utils.document_builder import build_qdrant_point
from models.api_models import BatchLinkRequest, LinkItem, IndexingStatus
from parsers.parser_factory import ParserFactory
from config import Config

logger = logging.getLogger(__name__)

class CollectionService:
    def __init__(self):
        self.qdrant_repo = QdrantRepository()
        self.embedding_client = embedding_client
        self.storage_service = GCSStorageService()

    def _get_user_collection(self, user_id: str) -> str:
        return f"user_{user_id}"

    async def process_batch(self, request: BatchLinkRequest, tenant_id: str):
        self.qdrant_repo.create_user_collection(tenant_id)

        results = []
        for item in request.items:
            try:
                # 1. Resolve Source
                source = self._resolve_source(item)
                
                # 2. Parse Content
                parsed = self._parse_content(source, item.type)
                
                # 3. Chunk Content
                chunks = self._chunk_content(parsed, item.type)
                
                # 4. Embed & Build Points
                points = self._embed_and_build_points(chunks, item, parsed)
                
                # 5. Index Points
                self._index_points(tenant_id, points)

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
        if item.type == 'file':
            if not item.gcs_url:
                raise ValueError("Missing gcs_url")
            
            if item.gcs_url.startswith(('http://', 'https://')):
                return self._download_from_url(item.gcs_url)
                
            return self._download_from_gcs(item.gcs_url)
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

    def _embed_and_build_points(self, chunks, item: LinkItem, parsed_content):
        points = []
        for chunk in chunks:
            embedding = self.embedding_client.generate_single_embedding(chunk.text)
            
            meta_channel = parsed_content.metadata.channel if item.type == 'youtube' else None
            meta_domain = parsed_content.metadata.domain if item.type == 'web' else None
            
            point = build_qdrant_point(
                collection_id=item.collection_id or "default", 
                file_id=item.file_id,
                chunk_id=chunk.chunk_id,
                chunk_text=chunk.text,
                embedding=embedding,
                source_type=item.type,
                file_name=parsed_content.metadata.title or "Unknown",
                chunk_type=chunk.chunk_metadata.chunk_type.value,
                youtube_channel=meta_channel,
                web_domain=meta_domain
            )
            points.append(point)
        
        if not points:
            raise ValueError("No chunks generated")
        return points

    def _index_points(self, tenant_id: str, points: List):
        user_col = self._get_user_collection(tenant_id)
        self.qdrant_repo.link_content(user_col, points)

    def _set_status(self, tenant_id: str, file_id: str, status: IndexingStatus, error: Optional[str] = None, item_name: Optional[str] = None, source_type: Optional[str] = None):
        user_col = self._get_user_collection(tenant_id)
        status_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{file_id}_status"))

        payload = {
            "type": "status",
            "file_id": file_id,
            "name": item_name,
            "source": source_type,
            "status": status.value,
            "error": error,
            "timestamp": datetime.utcnow().isoformat()
        }

        logger.info(f"[_set_status] Setting status for file_id={file_id}, status={status.value}, name={item_name}, source={source_type}")

        from qdrant_client.models import PointStruct
        vector_size = Config.embedding.VECTOR_SIZE
        point = PointStruct(id=status_id, vector=[0.0]*vector_size, payload=payload)

        try:
            self.qdrant_repo.client.upsert(user_col, points=[point])
            logger.info(f"[_set_status] Successfully upserted status point for file_id={file_id}")
        except Exception as e:
            logger.error(f"[_set_status] Failed to upsert status for file_id={file_id}: {e}", exc_info=True)

    def get_status(self, tenant_id: str, file_id: str) -> dict:
        user_col = self._get_user_collection(tenant_id)
        status_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{file_id}_status"))
        try:
            res = self.qdrant_repo.client.retrieve(user_col, ids=[status_id])
            return res[0].payload if res else {"status": "UNKNOWN", "file_id": file_id}
        except Exception as e:
            return {"status": "UNKNOWN", "error": str(e)}



    def unlink_content(self, collection_name: Optional[str], file_ids: List[str], user_id: str) -> int:
        user_col = self._get_user_collection(user_id)
        
        if not self.qdrant_repo.collection_exists(user_col):
            return 0

        deleted_count = 0

        for file_id in file_ids:
            try:
                # If deleting globally (collection_name is None), check if file exists via status point
                if collection_name is None:
                     status_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{file_id}_status"))
                     existing = self.qdrant_repo.client.retrieve(user_col, ids=[status_id])
                     
                     if not existing:
                         continue # File already deleted or doesn't exist
                         
                     self.qdrant_repo.client.delete(user_col, points_selector=[status_id])

                success = self.qdrant_repo.unlink_content(user_col, file_id=file_id, collection_id=collection_name)
                if success:
                    deleted_count += 1
            except Exception:
                logger.error(f"Error unlinking file {file_id}", exc_info=True)
        
        return deleted_count

    def delete_collection(self, user_id: str, collection_id: str) -> bool:
        return self.qdrant_repo.delete_logical_collection(user_id, collection_id)

    def purge_user_data(self, user_id: str) -> bool:
        user_col = self._get_user_collection(user_id)
        return self.qdrant_repo.delete_collection(user_col)
