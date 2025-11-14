from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import logging
from fastapi import BackgroundTasks
from repositories.qdrant_repository import QdrantRepository
from repositories.collection_repository import collection_repository
from repositories.quiz_repository import quiz_repository
from utils.embedding_client import EmbeddingClient
from services.file_service import file_service
from services.query_service import QueryService
from services.hierarchical_chunking_service import HierarchicalChunkingService
from services.user_service import user_service
from services.quiz_job_service import quiz_job_service
from services.quiz_generation_worker import quiz_generation_worker
from models.api_models import LinkContentItem, LinkContentResponse, ApiResponse, ApiResponseWithBody, QueryResponse, UnlinkContentResponse, BookMetadata, ContentType, QuizConfig
from models.quiz_models import QuizResponse
from models.quiz_job_models import QuizJobResponse
from config import Config
from utils.document_builder import build_chunk_document, build_content_document
from models.file_types import FileType
from strategies.content_strategy_selector import ContentStrategySelector

logger = logging.getLogger(__name__)

class CollectionService:
    def __init__(self):
        logger.info("Initializing CollectionService")
        self.qdrant_repo = QdrantRepository()
        self.collection_repo = collection_repository
        self.embedding_client = EmbeddingClient()
        self.file_service = file_service
        self.query_service = QueryService()
        self.chunking_service = HierarchicalChunkingService()
        self.strategy_selector = ContentStrategySelector()
        logger.debug("CollectionService initialized successfully")

    def _get_qdrant_collection_name(self, user_id: str, collection_name: str) -> str:
        """Generate Qdrant collection name with user prefix"""
        return f"{user_id}_{collection_name}"

    def create_collection(self, user_id: str, name: str, rag_config: Optional[Dict] = None, indexing_config: Optional[Dict] = None) -> ApiResponse:
        try:
            # Ensure user exists before creating collection
            if not user_service.ensure_user_exists(user_id):
                logger.warning(f"Failed to create user {user_id}, proceeding with collection creation anyway")

            # Check if collection already exists for this user
            if self.collection_repo.collection_exists(user_id, name):
                return ApiResponse(status="FAILURE", message="Collection already exists")

            # Create in Qdrant with user-prefixed name
            qdrant_name = self._get_qdrant_collection_name(user_id, name)
            success = self.qdrant_repo.create_collection(qdrant_name)

            if success:
                # Store in PostgreSQL
                db_success = self.collection_repo.create_collection(user_id, name, rag_config, indexing_config)
                if db_success:
                    return ApiResponse(status="SUCCESS", message="Collection created successfully")
                else:
                    # Rollback Qdrant collection if DB insert fails
                    self.qdrant_repo.delete_collection(qdrant_name)
                    return ApiResponse(status="FAILURE", message="Failed to save collection metadata")
            else:
                return ApiResponse(status="FAILURE", message="Failed to create collection in vector database")
        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            return ApiResponse(status="FAILURE", message=f"Failed to create collection: {str(e)}")

    def delete_collection(self, user_id: str, name: str) -> ApiResponse:
        try:
            if not self.collection_repo.collection_exists(user_id, name):
                return ApiResponse(status="FAILURE", message=f"Collection '{name}' does not exist")

            qdrant_name = self._get_qdrant_collection_name(user_id, name)

            # Step 1: Get all files in the collection before deletion
            logger.info(f"Getting all files in collection '{name}' for cleanup")
            try:
                embeddings_result = self.qdrant_repo.get_all_embeddings(qdrant_name, limit=1000, include_vectors=False)
                embeddings = embeddings_result.get("embeddings", [])

                # Extract unique file IDs
                file_ids = list(set([emb.get("document_id") for emb in embeddings if emb.get("document_id")]))

                if file_ids:
                    logger.info(f"Found {len(file_ids)} files to unlink from collection '{name}'")

                    # Step 2: Unlink all files from collection
                    unlink_success = self.qdrant_repo.unlink_content(qdrant_name, file_ids)
                    if unlink_success:
                        logger.info(f"Successfully unlinked {len(file_ids)} files from collection '{name}'")
                    else:
                        logger.warning(f"Failed to unlink some files from collection '{name}', proceeding with deletion")
                else:
                    logger.info(f"No files found in collection '{name}', proceeding with deletion")

            except Exception as e:
                logger.warning(f"Failed to clean up files in collection '{name}': {e}, proceeding with deletion")

            # Step 3: Delete from Qdrant
            qdrant_success = self.qdrant_repo.delete_collection(qdrant_name)

            # Step 4: Delete from PostgreSQL
            db_success = self.collection_repo.delete_collection(user_id, name)

            if qdrant_success and db_success:
                return ApiResponse(status="SUCCESS", message=f"Collection '{name}' and all linked files deleted successfully")
            else:
                return ApiResponse(status="FAILURE", message=f"Failed to delete collection '{name}' - check server logs for details")
        except Exception as e:
            logger.error(f"Failed to delete collection: {e}")
            return ApiResponse(status="FAILURE", message=f"Failed to delete collection: {str(e)}")

    def list_collections(self, user_id: str) -> ApiResponseWithBody:
        try:
            collections = self.collection_repo.list_collections(user_id)
            return ApiResponseWithBody(status="SUCCESS", message="Collections retrieved successfully", body={"collections": collections})
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return ApiResponseWithBody(status="FAILURE", message=f"Failed to list collections: {str(e)}", body={})

    def get_collection(self, user_id: str, name: str) -> ApiResponse:
        try:
            exists = self.collection_repo.collection_exists(user_id, name)
            if exists:
                return ApiResponse(status="SUCCESS", message=f"Collection '{name}' exists")
            else:
                return ApiResponse(status="FAILURE", message=f"Collection '{name}' not found")
        except Exception as e:
            logger.error(f"Failed to check collection: {e}")
            return ApiResponse(status="FAILURE", message=f"Failed to check collection: {str(e)}")

    def _validate_file_exists(self, file_id: str, user_id: str) -> bool:
        return self.file_service.file_exists(file_id, user_id)

    def _validate_collection_exists(self, user_id: str, collection_name: str) -> bool:
        return self.collection_repo.collection_exists(user_id, collection_name)

    def _get_file_content(self, file_id: str, user_id: str) -> Optional[str]:
        return self.file_service.get_file_content(file_id, user_id)

    def _generate_embedding_and_document(
        self,
        file_id: str,
        file_content: str,
        file_type: str,
        user_id: str,
        content_type_hint: Optional[ContentType] = None,
        book_metadata_hint: Optional[BookMetadata] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Generate embeddings and documents using adaptive chunking strategy.

        Args:
            file_id: Unique file identifier
            file_content: Raw file content
            file_type: Type of file (pdf, text, etc.)
            user_id: User identifier
            content_type_hint: Optional user-provided content type
            book_metadata_hint: Optional user-provided book metadata

        Returns:
            List of documents with embeddings and metadata
        """
        try:
            documents = []

            file_type_normalized = file_type.lower().strip()
            logger.info(f"file type (normalized): {file_type_normalized}")

            supported_types = [FileType.PDF.value, FileType.TEXT.value]
            if file_type_normalized in supported_types:
                logger.info(f"Getting local file path for file_id={file_id}, user_id={user_id}")
                file_path = self.file_service.get_local_file_for_processing(file_id, user_id)
                if not file_path:
                    logger.error(f"CRITICAL: get_local_file_for_processing returned None for file_id={file_id}")
                    return None

                storage_path = self.file_service.get_file_path(file_id, user_id)
                is_temp_file = not self.file_service._is_local_storage(storage_path)
                logger.info(f"File path resolved: {file_path}, is_temp_file: {is_temp_file}")

                try:
                    # STRATEGY PATTERN: Detect content type and select strategy
                    content_type = self.strategy_selector.detect_content_type(
                        file_path,
                        user_hint=content_type_hint
                    )
                    logger.info(f"Detected content type: {content_type.value}")

                    # Get appropriate strategy
                    strategy = self.strategy_selector.get_strategy(content_type)
                    logger.info(f"Using strategy: {strategy}")

                    # Extract metadata from document
                    extracted_metadata = strategy.extract_metadata(file_path)
                    logger.info(f"Extracted metadata: {extracted_metadata}")

                    # Merge extracted metadata with user-provided metadata
                    book_metadata = self._merge_book_metadata(
                        extracted_metadata,
                        book_metadata_hint
                    )

                    # Chunk document using strategy
                    chunks = strategy.chunk_document(
                        file_path=file_path,
                        document_id=file_id,
                        hierarchical_chunker=self.chunking_service,
                        book_metadata=book_metadata
                    )
                    logger.info(f"Chunking completed. Generated {len(chunks) if chunks else 0} chunks")
                except Exception as e:
                    logger.error(f"Exception during chunking: {e}", exc_info=True)
                    chunks = []
                finally:
                    if is_temp_file:
                        import os
                        logger.info(f"Cleaning up temp file: {file_path}")
                        try:
                            os.unlink(file_path)
                        except Exception as e:
                            logger.error(f"Failed to cleanup temp file {file_path}: {e}")

                    if not chunks:
                        logger.warning(f"No chunks generated for {file_id}, falling back to full document")
                        embedding = self.embedding_client.generate_single_embedding(file_content)
                        return [build_content_document(file_id, file_type, file_content, embedding)]

                    # Generate embeddings and build documents
                    for chunk in chunks:
                        embedding = self.embedding_client.generate_single_embedding(chunk.text)
                        doc = build_chunk_document(
                            file_id=file_id,
                            file_type=file_type,
                            chunk=chunk,
                            embedding=embedding,
                            book_metadata=book_metadata,
                            content_type=content_type
                        )
                        documents.append(doc)

                    logger.info(
                        f"Generated {len(documents)} chunks for {file_id} "
                        f"using {content_type.value} strategy ({strategy.chunk_size} chars)"
                    )

                finally:
                    # Clean up temp file
                    if is_temp_file:
                        import os
                        try:
                            os.unlink(file_path)
                            logger.debug(f"Cleaned up temp file: {file_path}")
                        except Exception as e:
                            logger.warning(f"Failed to clean up temp file {file_path}: {e}")

            else:
                # Non-PDF/text files: use simple embedding
                embedding = self.embedding_client.generate_single_embedding(file_content)
                documents = [build_content_document(file_id, file_type, file_content, embedding)]

            return documents

        except Exception as e:
            logger.error(f"Error generating embeddings for {file_id}: {e}", exc_info=True)
            return None

    def _merge_book_metadata(
        self,
        extracted: Dict[str, Any],
        user_provided: Optional[BookMetadata]
    ) -> Optional[BookMetadata]:
        """
        Merge extracted and user-provided book metadata.

        User-provided metadata takes precedence over extracted.

        Args:
            extracted: Metadata extracted from PDF
            user_provided: User-provided metadata

        Returns:
            Merged BookMetadata or None
        """
        # If no metadata at all, return None
        if not extracted and not user_provided:
            return None

        # Start with extracted metadata
        merged = BookMetadata(
            book_id=extracted.get("book_id"),
            book_title=extracted.get("book_title"),
            book_authors=extracted.get("book_authors", []),
            book_edition=extracted.get("book_edition"),
            book_subject=extracted.get("book_subject"),
            total_chapters=extracted.get("total_chapters"),
            total_pages=extracted.get("total_pages")
        )

        # Override with user-provided values
        if user_provided:
            if user_provided.book_id:
                merged.book_id = user_provided.book_id
            if user_provided.book_title:
                merged.book_title = user_provided.book_title
            if user_provided.book_authors:
                merged.book_authors = user_provided.book_authors
            if user_provided.book_edition:
                merged.book_edition = user_provided.book_edition
            if user_provided.book_subject:
                merged.book_subject = user_provided.book_subject
            if user_provided.total_chapters:
                merged.total_chapters = user_provided.total_chapters
            if user_provided.total_pages:
                merged.total_pages = user_provided.total_pages

        # Only return if we have at least some metadata
        if merged.book_title or merged.book_id or merged.book_authors:
            return merged

        return None

    def _check_file_already_linked(self, user_id: str, collection_name: str, file_id: str) -> bool:
        try:
            qdrant_collection_name = self._get_qdrant_collection_name(user_id, collection_name)
            status = self.qdrant_repo.batch_read_files(qdrant_collection_name, [file_id])
            return status.get(file_id) == "indexed"
        except Exception:
            return False

    def _create_link_error_response(self, file_item: LinkContentItem, status_code: int, message: str) -> LinkContentResponse:
        return LinkContentResponse(
            name=file_item.name,
            file_id=file_item.file_id,
            type=file_item.type,
            created_at=None,
            indexing_status="INDEXING_FAILED",
            status_code=status_code,
            message=message
        )

    def _create_link_success_response(self, file_item: LinkContentItem) -> LinkContentResponse:
        return LinkContentResponse(
            name=file_item.name,
            file_id=file_item.file_id,
            type=file_item.type,
            created_at=datetime.now().isoformat(),
            indexing_status="INDEXING_SUCCESS",
            status_code=200,
            message="Successfully linked to collection"
        )

    def _create_unlink_response(self, file_id: str, status_code: int, message: str) -> UnlinkContentResponse:
        return UnlinkContentResponse(
            file_id=file_id,
            status_code=status_code,
            message=message
        )


    def link_content(self, collection_name: str, files: List[LinkContentItem], user_id: str) -> List[LinkContentResponse]:
        logger.info(f"Linking {len(files)} files to collection '{collection_name}' for user '{user_id}'")
        responses = []

        if not self._validate_collection_exists(user_id, collection_name):
            logger.error(f"Collection '{collection_name}' does not exist for user '{user_id}'")
            for file_item in files:
                responses.append(self._create_link_error_response(
                    file_item, 404, f"Collection '{collection_name}' does not exist"
                ))
            return responses

        # Get the actual Qdrant collection name
        qdrant_collection_name = self._get_qdrant_collection_name(user_id, collection_name)

        for file_item in files:
            try:
                logger.debug(f"Processing link for file {file_item.file_id}")

                if not self._validate_file_exists(file_item.file_id, user_id):
                    logger.warning(f"File {file_item.file_id} not found")
                    responses.append(self._create_link_error_response(file_item, 404, "File not found"))
                    continue

                if self._check_file_already_linked(user_id, collection_name, file_item.file_id):
                    logger.warning(f"File {file_item.file_id} already linked to collection '{collection_name}'")
                    responses.append(self._create_link_error_response(file_item, 409, "File already linked, unlink first"))
                    continue

                file_content = self._get_file_content(file_item.file_id, user_id)
                if not file_content:
                    logger.error(f"Could not read content for file {file_item.file_id}")
                    responses.append(self._create_link_error_response(file_item, 500, "Could not read file content"))
                    continue

                logger.info(f"Generating embedding for file {file_item.file_id}")
                file_type_normalized = file_item.type.lower().strip()
                documents = self._generate_embedding_and_document(
                    file_id=file_item.file_id,
                    file_content=file_content,
                    file_type=file_item.type,
                    user_id=user_id,
                    content_type_hint=file_item.content_type,  # Pass user hint
                    book_metadata_hint=file_item.book_metadata  # Pass user metadata
                )
                if not documents:
                    logger.error(f"Failed to generate embedding for file {file_item.file_id}")
                    responses.append(self._create_link_error_response(file_item, 500, "Failed to generate embedding"))
                    continue

                logger.debug(f"Linking file {file_item.file_id} to collection '{qdrant_collection_name}'")
                success = self.qdrant_repo.link_content(qdrant_collection_name, documents)
                if success:
                    logger.info(f"Successfully linked file {file_item.file_id} to collection '{collection_name}'")
                    responses.append(self._create_link_success_response(file_item))
                else:
                    logger.error(f"Failed to link file {file_item.file_id} to collection '{collection_name}' - repository returned False")
                    responses.append(self._create_link_error_response(file_item, 500, "Failed to link content to collection"))

            except Exception as e:
                logger.error(f"Exception while linking file {file_item.file_id}: {str(e)}")
                logger.exception("Full exception details:")
                responses.append(self._create_link_error_response(file_item, 500, f"Internal error: {str(e)}"))

        logger.info(f"Completed link operation for collection '{collection_name}'. Processed {len(responses)} files")
        return responses

    def unlink_content(self, collection_name: str, file_ids: List[str], user_id: str) -> List[UnlinkContentResponse]:
        logger.info(f"Unlinking {len(file_ids)} files from collection '{collection_name}' for user '{user_id}'")
        responses = []

        if not self._validate_collection_exists(user_id, collection_name):
            logger.error(f"Collection '{collection_name}' does not exist for user '{user_id}'")
            for file_id in file_ids:
                responses.append(self._create_unlink_response(file_id, 404, f"Collection '{collection_name}' does not exist"))
            return responses

        # Get the actual Qdrant collection name
        qdrant_collection_name = self._get_qdrant_collection_name(user_id, collection_name)

        for file_id in file_ids:
            try:
                logger.debug(f"Processing unlink for file {file_id}")

                if not self._check_file_already_linked(user_id, collection_name, file_id):
                    logger.warning(f"File {file_id} not found in collection '{collection_name}'")
                    responses.append(self._create_unlink_response(file_id, 404, "File not found in collection"))
                    continue

                logger.debug(f"File {file_id} found in collection, proceeding with unlink")
                success = self.qdrant_repo.unlink_content(qdrant_collection_name, [file_id])
                if success:
                    logger.info(f"Successfully unlinked file {file_id} from collection '{collection_name}'")
                    responses.append(self._create_unlink_response(file_id, 200, "Successfully unlinked from collection"))
                else:
                    logger.error(f"Failed to unlink file {file_id} from collection '{collection_name}' - repository returned False")
                    responses.append(self._create_unlink_response(file_id, 500, "Failed to unlink content from collection"))

            except Exception as e:
                logger.error(f"Exception while unlinking file {file_id}: {str(e)}")
                logger.exception("Full exception details:")
                responses.append(self._create_unlink_response(file_id, 500, f"Internal error: {str(e)}"))

        logger.info(f"Completed unlink operation for collection '{collection_name}'. Processed {len(responses)} files")
        return responses

    def query_collection(self, user_id: str, collection_name: str, query_text: str, enable_critic: bool = True, structured_output: bool = False, quiz_config: Optional[QuizConfig] = None, background_tasks: Optional[BackgroundTasks] = None) -> Union[QueryResponse, QuizResponse, QuizJobResponse]:
        # Create error response based on mode
        def create_error_response(message: str):
            if quiz_config is not None:
                # Return quiz error response
                from models.quiz_models import QuizData, QuizMetadata, QuizSource, ContentSummary, ScoringInfo, GenerationMetadata
                import time

                quiz_metadata = QuizMetadata(
                    quiz_id="error",
                    title="Quiz Generation Error",
                    difficulty="unknown",
                    estimated_time_minutes=0,
                    total_questions=0,
                    max_score=0,
                    created_at=time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
                    source=QuizSource(type="collection", collection_name=collection_name, source_count=0)
                )

                return QuizResponse(
                    quiz_data=QuizData(
                        quiz_metadata=quiz_metadata,
                        questions=[],
                        content_summary=ContentSummary(
                            main_summary=message,
                            key_concepts=[],
                            topics_covered=[],
                            prerequisite_knowledge=[]
                        ),
                        scoring_info=ScoringInfo(
                            total_score=0,
                            passing_score=0,
                            time_limit_minutes=0
                        )
                    ),
                    generation_metadata=GenerationMetadata(
                        confidence=0.0,
                        is_relevant=False,
                        generation_time_ms=0,
                        model_used="unknown",
                        content_sources=[]
                    )
                )
            else:
                return QueryResponse(
                    answer=message,
                    confidence=0.0,
                    is_relevant=False,
                    chunks=[]
                )

        if not self._validate_collection_exists(user_id, collection_name):
            return create_error_response("Context not found")

        if not query_text.strip():
            return create_error_response("Context not found")

        # Check if this is a quiz request - make it async
        if quiz_config is not None:
            # Create async quiz generation job
            quiz_job_response = quiz_job_service.create_quiz_job(
                user_id=user_id,
                collection_name=collection_name,
                query_text=query_text,
                quiz_config=quiz_config
            )

            # Start background task if available
            if background_tasks:
                background_tasks.add_task(
                    quiz_generation_worker.generate_quiz_async,
                    quiz_job_response.quiz_job_id
                )
                logger.info(f"Started background quiz generation for job {quiz_job_response.quiz_job_id}")
            else:
                # Fallback: start task manually (for testing)
                import threading
                thread = threading.Thread(
                    target=quiz_generation_worker.generate_quiz_async,
                    args=(quiz_job_response.quiz_job_id,)
                )
                thread.daemon = True
                thread.start()
                logger.info(f"Started threaded quiz generation for job {quiz_job_response.quiz_job_id}")

            return quiz_job_response
        else:
            # Regular synchronous query
            qdrant_collection_name = self._get_qdrant_collection_name(user_id, collection_name)
            return self.query_service.search(qdrant_collection_name, query_text, 10, enable_critic, structured_output, quiz_config)

    def get_collection_embeddings(self, user_id: str, collection_name: str, limit: int = 100, offset: Optional[str] = None, include_vectors: bool = False):
        """Retrieve all embeddings from a collection with pagination"""
        try:
            # Validate collection exists and user has access
            if not self._validate_collection_exists(user_id, collection_name):
                return {
                    "status": "FAILURE",
                    "message": f"Collection '{collection_name}' does not exist",
                    "body": {}
                }

            # Get the actual Qdrant collection name
            qdrant_collection_name = self._get_qdrant_collection_name(user_id, collection_name)

            # Call repository to get embeddings
            logger.info(f"Getting embeddings for collection '{collection_name}' for user '{user_id}'")
            result = self.qdrant_repo.get_all_embeddings(
                collection_name=qdrant_collection_name,
                limit=limit,
                offset=offset,
                include_vectors=include_vectors
            )

            if "error" in result:
                return {
                    "status": "FAILURE",
                    "message": f"Failed to retrieve embeddings: {result['error']}",
                    "body": {}
                }

            logger.info(f"Successfully retrieved {len(result['embeddings'])} embeddings from collection '{collection_name}'")

            return {
                "status": "SUCCESS",
                "message": "Embeddings retrieved successfully",
                "body": result
            }

        except Exception as e:
            logger.error(f"Failed to get embeddings from collection '{collection_name}' for user '{user_id}': {e}")
            logger.exception("Full exception details:")
            return {
                "status": "FAILURE",
                "message": f"Internal error: {str(e)}",
                "body": {}
            }

