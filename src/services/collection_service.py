from typing import List, Dict, Any, Optional
import logging
from fastapi import BackgroundTasks

from repositories.qdrant_repository import QdrantRepository
from services.file_service import file_service
from services.hierarchical_chunking_service import chunking_service
from utils.embedding_client import embedding_client
from utils.document_builder import build_qdrant_point
from models.api_models import LinkContentItem, LinkContentResponse, UnlinkContentResponse, QuizConfig, QueryResponse
from models.quiz_models import QuizResponse
from models.quiz_job_models import QuizJobResponse
from parsers.parser_factory import ParserFactory
from config import Config

logger = logging.getLogger(__name__)

class CollectionService:
    def __init__(self):
        logger.info("Initializing CollectionService")
        self.qdrant_repo = QdrantRepository()
        self.embedding_client = embedding_client

    def _get_qdrant_collection_name(self, user_id: str) -> str:
        """Get the per-user Qdrant collection name"""
        return f"user_{user_id}"

    async def link_content(self, collection_name: str, files: List[LinkContentItem], user_id: str) -> List[LinkContentResponse]:
        """
        Link content (files, URLs) to a logical collection (folder).
        Content is stored in user_{user_id} collection with collection_id=collection_name.
        """
        results = []
        user_collection = self._get_qdrant_collection_name(user_id)

        # Ensure user's Qdrant collection exists
        self.qdrant_repo.create_user_collection(user_id)

        for item in files:
            try:
                # 1. Determine Source & Parser
                source_content = None
                parser_type = "pdf" # Default
                source_identifier = item.file_id

                if item.youtube_url:
                    parser_type = "youtube"
                    source_identifier = item.youtube_url
                elif item.web_url:
                    parser_type = "web"
                    source_identifier = item.web_url
                elif item.file_id:
                     # For files, we need to get the local path
                     # Assuming item.name is the filename, pass it to file_service
                     # Note: file_service needs update to accept optional filename or we rely on file_id
                     # if file_service is stateless, we might need to rely on convention or item.name
                     # using get_local_file_for_processing which currently might use DB.
                     # We'll update file_service later to handle this gracefully.
                     source_identifier = file_service.get_local_file_for_processing(item.file_id, user_id)
                     if not source_identifier:
                         raise ValueError(f"File not found: {item.file_id}")
                else:
                    raise ValueError("No valid source provided (file_id, youtube_url, or web_url)")

                # 2. Parse Content
                # PDF uses legacy chunking_service for now (as per plan to preserve strategies)
                # YouTube/Web use new ParserFactory
                
                points = []

                if parser_type == "pdf":
                    # LEGACY PATH for PDF (Preserving existing chunking strategies)
                    file_content = file_service.get_file_content(item.file_id, user_id) # This might fail if file_service needs DB
                    # Actually, better to read from source_identifier path if possible
                    # But get_file_content works on file_id.
                    # We will rely on file_service updates.
                    
                    if not file_content:
                         # Try reading from path if get_file_content fails (redundancy)
                         if source_identifier and str(source_identifier).endswith('.pdf'):
                             with open(source_identifier, 'rb') as f:
                                 raw_data = f.read()
                                 file_content = file_service.extract_pdf_text(raw_data)
                    
                    if not file_content:
                        raise ValueError("Could not extract text from file")

                    # Chunking
                    chunks = chunking_service.chunk_text(
                        text=file_content,
                        file_type="pdf",
                        book_metadata=None # Metadata not passed in link request currently
                    )

                    # Embed & Build Points
                    for chunk in chunks:
                        embedding = self.embedding_client.generate_embedding(chunk.text)
                        
                        point = build_qdrant_point(
                            collection_id=collection_name, # Logical folder
                            file_id=item.file_id,
                            chunk_id=chunk.chunk_id,
                            chunk_text=chunk.text,
                            embedding=embedding,
                            source_type="pdf",
                            file_name=item.name,
                            chunk_type=chunk.chunk_metadata.chunk_type.value,
                            page_number=chunk.topic_metadata.page_start
                        )
                        points.append(point)

                else:
                    # NEW PARSER PATH (YouTube/Web)
                    parser = ParserFactory.get_parser(parser_type, gemini_api_key=Config.llm.GEMINI_API_KEY)
                    parsed_content = parser.parse(source_identifier)
                    
                    # Simple chunking for parsed content (since no specific chunker for them yet in plan?)
                    # Plan says "Step 12: ... chunks = chunker.chunk(parsed_content)"
                    # We need a chunker for ParsedContent.
                    # reusing chunking_service.chunk_text doesn't fit ParsedContent object directly.
                    # Implementation Gap: We need to adapt ParsedContent to chunks.
                    # For now, let's treat parsed_content.text as plain text and use chunking_service?
                    # Or iterate sections.
                    
                    # Let's iterate sections and chunk them if needed, or treat sections as chunks.
                    # For simplicity and robustness, let's use chunking_service on the full text 
                    # OR if sections are granular enough, use them.
                    # Plan Step 12 implies a `chunker.chunk(parsed_content)` exists but it was not defined in "Files to Create".
                    # I'll manually chunk the text using existing service for consistency.
                    
                    chunks = chunking_service.chunk_text(
                        text=parsed_content.text, 
                        file_type=parser_type
                    )

                    for chunk in chunks:
                        embedding = self.embedding_client.generate_embedding(chunk.text)
                        
                        point = build_qdrant_point(
                            collection_id=collection_name, 
                            file_id=item.file_id or str(hash(source_identifier)), # Fallback for URL
                            chunk_id=chunk.chunk_id,
                            chunk_text=chunk.text,
                            embedding=embedding,
                            source_type=parser_type,
                            file_name=item.name,
                            chunk_type=chunk.chunk_metadata.chunk_type.value,
                            # We lose some metadata here (timestamp/page) by re-chunking plain text
                            # But it ensures vectors are compatible.
                            # Future: Improve chunker to respect ParsedContent structure.
                            youtube_channel=parsed_content.metadata.channel if parser_type == 'youtube' else None,
                            web_domain=parsed_content.metadata.domain if parser_type == 'web' else None
                        )
                        points.append(point)

                # 3. Store in Qdrant
                if points:
                    # Convert dict points to PointStruct handled by repo or passing dicts?
                    # Repo `link_content` expects list of dicts with `document_id` etc, 
                    # BUT `build_qdrant_point` returns exactly that schema!
                    # And `qdrant_repo.link_content` calls `_create_point_from_document` which expects that dict.
                    # Wait, `qdrant_repo.link_content` might need update if `build_qdrant_point` returns something different
                    # `build_qdrant_point` returns { document_id, chunk_id, text, source, vector, metadata }
                    # `qdrant_repo._create_point_from_document` uses: doc.get("text"), doc.get("vector"), doc.get("metadata")
                    # It seems compatible.
                    
                    # We upload to user_collection, NOT collection_name (which is just a tag now)
                    # But repo method signature is `link_content(collection_name, ...)`
                    # So we pass `user_collection` as the name.
                    success = self.qdrant_repo.link_content(user_collection, points)
                    
                    if success:
                        results.append(LinkContentResponse(file_id=item.file_id or "url", status="success", message="Linked successfully"))
                    else:
                        results.append(LinkContentResponse(file_id=item.file_id or "url", status="failed", message="Failed to store vectors"))
                else:
                     results.append(LinkContentResponse(file_id=item.file_id or "url", status="failed", message="No content extracted"))

            except Exception as e:
                logger.error(f"Error linking item {item.name}: {e}")
                results.append(LinkContentResponse(
                    file_id=item.file_id or "unknown", 
                    status="failed", 
                    message=str(e)
                ))

        return results

    def unlink_content(self, collection_name: str, file_ids: List[str], user_id: str) -> List[UnlinkContentResponse]:
        """
        Unlink content from a logical collection.
        Deletes points from user_{user_id} where collection_id=collection_name AND file_id IN file_ids.
        """
        results = []
        user_collection = self._get_qdrant_collection_name(user_id)

        for file_id in file_ids:
            try:
                # Use filtered delete in Qdrant
                # We need to delete where metadata.collection_id == collection_name AND metadata.file_id == file_id
                
                # We can use qdrant_repo.unlink_content with new filters
                success = self.qdrant_repo.unlink_content(
                    collection_name=user_collection,
                    file_id=file_id,
                    collection_id=collection_name
                )

                if success:
                    results.append(UnlinkContentResponse(file_id=file_id, status="success", message="Unlinked successfully"))
                else:
                    results.append(UnlinkContentResponse(file_id=file_id, status="failed", message="Failed to delete vectors"))

            except Exception as e:
                logger.error(f"Error unlinking file {file_id}: {e}")
                results.append(UnlinkContentResponse(file_id=file_id, status="failed", message=str(e)))
        
        return results

    def query_collection(
        self,
        user_id: str,
        collection_name: str,
        query_text: str,
        enable_critic: bool = True,
        structured_output: bool = False,
        quiz_config: Optional[QuizConfig] = None,
        background_tasks: Optional[BackgroundTasks] = None
    ) -> Any: # Returns QueryResponse, QuizResponse or QuizJobResponse
        
        # We delegate to QueryService, but we need to ensure QueryService uses correct filters.
        # Since QueryService is initialized elsewhere or we can instantiate it here?
        # Typically Service uses other Services.
        # But `collection_service` logic for query was mainly wrapper.
        
        from services.query_service import QueryService
        query_service = QueryService() # Or dependency injection
        
        # We pass collection_name as 'collection_id' filter logic, 
        # but the query_service.search expects `collection_name` as the PHYSICAL Qdrant collection.
        # So we must pass `user_{user_id}` as collection_name, 
        # and `collection_name` (logical) as `collection_id` filter.
        
        user_collection = self._get_qdrant_collection_name(user_id)
        
        # We need to update QueryService.search signature or logic to accept logical collection_id!
        # I will update QueryService next. Assuming it will have `collection_id` param.
        
        return query_service.search(
            collection_name=user_collection, 
            query_text=query_text,
            enable_critic=enable_critic,
            structured_output=structured_output,
            quiz_config=quiz_config,
            collection_id=collection_name # This arg needs to be added to QueryService.search
        )

    def purge_user_data(self, user_id: str) -> bool:
        """
        Delete the entire Qdrant collection for a user.
        """
        user_collection = self._get_qdrant_collection_name(user_id)
        return self.qdrant_repo.delete_collection(user_collection)
