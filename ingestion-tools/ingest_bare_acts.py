"""
Bare Acts Ingestion Script
Loads parsed bare acts JSON and ingests into Neo4j with hierarchical structure.

Enhanced with:
- Robust error handling with retries
- Validation of parsed data before ingestion
- Progress tracking and detailed logging
- Graceful handling of partial failures
"""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import uuid
import hashlib
import traceback

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.graph_service import get_graph_service
from src.repositories.neo4j_repository import neo4j_repository
from src.utils.embedding_client import embedding_client
from src.models.api_models import HierarchicalChunk, ChunkMetadata, TopicMetadata, ChunkType
from src.config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
COLLECTION_ID = "bare-acts-golden-source"
USER_ID = "system"
CONTENT_TYPE = "legal"
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


class IngestionError(Exception):
    """Custom exception for ingestion errors."""
    pass


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


def retry_on_failure(max_retries: int = MAX_RETRIES, delay: float = RETRY_DELAY):
    """Decorator for retrying failed operations."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}. Retrying in {delay}s...")
                        time.sleep(delay)
                    else:
                        logger.error(f"All {max_retries} attempts failed for {func.__name__}")
            raise last_exception
        return wrapper
    return decorator


class BareActsIngestionRunner:
    """Ingests parsed bare acts into Neo4j with robust error handling."""
    
    def __init__(self, parsed_dir: str = "output"):
        self.parsed_dir = Path(parsed_dir)
        self.graph_service = None
        self.stats = {
            "acts_processed": 0,
            "chapters_created": 0,
            "sections_created": 0,
            "chunks_indexed": 0,
            "embeddings_generated": 0,
            "errors": [],
            "warnings": [],
            "skipped": []
        }
        self._initialized = False
    
    def _init_services(self) -> bool:
        """Initialize graph service with validation."""
        if self._initialized:
            return True
            
        try:
            self.graph_service = get_graph_service()
            if not self.graph_service:
                raise IngestionError("Failed to initialize graph service - returned None")
            
            # Verify connection
            test_result = self.graph_service.execute_query("RETURN 1 as test")
            if not test_result or test_result[0].get('test') != 1:
                raise IngestionError("Neo4j connection test failed")
            
            logger.info("✅ Graph service initialized and verified")
            self._initialized = True
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")
            self.stats["errors"].append(f"Service initialization failed: {str(e)}")
            return False
    
    def _validate_act_data(self, act_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate parsed act data before ingestion."""
        errors = []
        warnings = []
        
        # Required fields - only name is truly required
        if not act_data.get("name"):
            errors.append("Missing required field: name")
        
        # Validate year (warning only if missing/unusual)
        year = act_data.get("year", 0)
        if not isinstance(year, int) or year < 1800 or year > 2100:
            warnings.append(f"Unusual or missing year value: {year}")
        
        # Validate sections
        sections = act_data.get("sections", [])
        if not sections:
            errors.append("No sections found in parsed data")
        else:
            # Check for empty sections
            empty_sections = [s for s in sections if not s.get("content", "").strip() and not s.get("title", "").strip()]
            if len(empty_sections) > len(sections) * 0.3:  # More than 30% empty
                warnings.append(f"{len(empty_sections)} of {len(sections)} sections are empty")
        
        # Check for duplicate section numbers
        section_numbers = [s.get("number") for s in sections if s.get("number")]
        if len(section_numbers) != len(set(section_numbers)):
            warnings.append("Duplicate section numbers detected")
        
        # Log warnings
        for w in warnings:
            logger.warning(f"Validation warning: {w}")
            self.stats["warnings"].append(w)
        
        return len(errors) == 0, errors
    
    def _load_json_file(self, json_path: Path) -> Optional[Dict[str, Any]]:
        """Load and validate a single JSON file."""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            data['_source_file'] = json_path.name
            data['_file_path'] = str(json_path)
            
            # Basic validation
            is_valid, errors = self._validate_act_data(data)
            if not is_valid:
                for err in errors:
                    logger.error(f"Validation error in {json_path.name}: {err}")
                    self.stats["errors"].append(f"Validation: {json_path.name} - {err}")
                return None
            
            logger.info(f"Loaded: {data.get('name', json_path.name)} - {data.get('total_sections', 0)} sections")
            return data
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {json_path}: {e}")
            self.stats["errors"].append(f"JSON parse error: {json_path.name}")
            return None
        except Exception as e:
            logger.error(f"Failed to load {json_path}: {e}")
            self.stats["errors"].append(f"Load error: {json_path.name} - {str(e)}")
            return None
    
    def _load_json_files(self) -> List[Dict[str, Any]]:
        """Load all parsed JSON files from directory."""
        if not self.parsed_dir.exists():
            logger.error(f"Parsed directory does not exist: {self.parsed_dir}")
            return []
        
        json_files = list(self.parsed_dir.glob("*.json"))
        logger.info(f"Found {len(json_files)} JSON files to process")
        
        parsed_acts = []
        for json_file in json_files:
            data = self._load_json_file(json_file)
            if data:
                parsed_acts.append(data)
        
        return parsed_acts
    
    def _generate_statute_id(self, act_data: Dict[str, Any]) -> str:
        """Generate a consistent statute ID."""
        name = act_data.get('name', 'unknown').lower()
        # Clean the name for ID
        name_clean = ''.join(c if c.isalnum() or c == ' ' else '' for c in name)
        name_clean = name_clean.replace(' ', '_')
        year = act_data.get('year', 0)
        return f"statute_{name_clean}_{year}"
    
    def _generate_file_id(self, act_data: Dict[str, Any]) -> str:
        """Generate a consistent file ID for chunks."""
        name = act_data.get('name', 'unknown').lower()
        name_clean = ''.join(c if c.isalnum() or c == ' ' else '' for c in name)
        name_clean = name_clean.replace(' ', '_')
        year = act_data.get('year', 0)
        return f"bare_act_{name_clean}_{year}"
    
    def _generate_content_hash(self, act_data: Dict[str, Any]) -> str:
        """Generate a hash of the content for deduplication."""
        content = json.dumps(act_data.get("sections", []), sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    @retry_on_failure(max_retries=3, delay=1)
    def _clean_statute_data(self, statute_id: str, file_id: str):
        """Clean data for a specific statute with retry."""
        logger.info(f"Cleaning existing data for statute: {statute_id}...")
        
        try:
            # Delete chunks for this file_id
            result = self.graph_service.execute_query("""
                MATCH (c:Chunk {file_id: $file_id})
                DETACH DELETE c
                RETURN count(*) as deleted
            """, {"file_id": file_id})
            chunks_deleted = result[0]['deleted'] if result else 0
            
            # Delete the statute and its specific chapters/sections
            result = self.graph_service.execute_query("""
                MATCH (s:Statute {id: $statute_id})
                OPTIONAL MATCH (s)-[:HAS_CHAPTER]->(ch:Chapter)
                OPTIONAL MATCH (s)-[:HAS_SECTION]->(sec:Section)
                WITH s, collect(ch) as chapters, collect(sec) as sections
                DETACH DELETE s
                FOREACH (ch IN chapters | DETACH DELETE ch)
                FOREACH (sec IN sections | DETACH DELETE sec)
                RETURN 1 as done
            """, {"statute_id": statute_id})
            
            logger.info(f"Cleaned: {chunks_deleted} chunks deleted for {statute_id}")
            
        except Exception as e:
            logger.warning(f"Clean operation warning for {statute_id}: {e}")
            # Don't raise - cleaning failures shouldn't stop ingestion
    
    @retry_on_failure(max_retries=3, delay=1)
    def _create_collection(self):
        """Create the bare-acts collection with retry."""
        logger.info(f"Creating/verifying collection: {COLLECTION_ID}")
        
        # Compatible with Neo4j 4.x and 5.x
        self.graph_service.execute_query("""
            MERGE (u:User {user_id: $user_id})
            MERGE (c:Collection {collection_id: $collection_id})
            SET c.content_type = $content_type,
                c.is_public = true,
                c.name = 'Indian Bare Acts',
                c.description = 'Collection of Indian Bare Acts and Statutes',
                c.updated_at = datetime(),
                c.created_at = COALESCE(c.created_at, datetime())
            MERGE (u)-[:OWNS]->(c)
        """, {
            "user_id": USER_ID,
            "collection_id": COLLECTION_ID,
            "content_type": CONTENT_TYPE
        })
        logger.info(f"Collection {COLLECTION_ID} created/verified")
    
    @retry_on_failure(max_retries=3, delay=1)
    def _create_statute_node(self, act_data: Dict[str, Any], statute_id: str) -> bool:
        """Create a Statute node for the bare act."""
        try:
            self.graph_service.execute_query("""
                MERGE (s:Statute {id: $statute_id})
                SET s.name = $name,
                    s.year = $year,
                    s.act_number = $act_number,
                    s.document_type = 'bare_act',
                    s.total_chapters = $total_chapters,
                    s.total_sections = $total_sections,
                    s.preamble = $preamble,
                    s.content_hash = $content_hash,
                    s.source_file = $source_file,
                    s.indexed_at = datetime()
            """, {
                "statute_id": statute_id,
                "name": act_data.get("name", ""),
                "year": act_data.get("year", 0),
                "act_number": act_data.get("act_number", ""),
                "total_chapters": act_data.get("total_chapters", 0),
                "total_sections": act_data.get("total_sections", 0),
                "preamble": (act_data.get("preamble", "") or "")[:2000],
                "content_hash": self._generate_content_hash(act_data),
                "source_file": act_data.get("_source_file", "")
            })
            
            logger.info(f"Created statute: {act_data['name']} ({act_data.get('year', 'N/A')})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create statute node: {e}")
            raise
    
    def _create_chapter_nodes(self, act_data: Dict[str, Any], statute_id: str) -> Dict[str, str]:
        """Create Chapter nodes and link to Statute."""
        chapter_ids = {}
        
        # Deduplicate chapters (keep ones with sections)
        seen_chapters = {}
        for chapter in act_data.get("chapters", []):
            ch_num = chapter.get("number", "")
            if not ch_num:
                continue
            if ch_num not in seen_chapters or chapter.get("section_numbers"):
                seen_chapters[ch_num] = chapter
        
        for chapter in seen_chapters.values():
            ch_num = chapter.get("number", "")
            ch_title = chapter.get("title", "")
            chapter_id = f"{statute_id}_chapter_{ch_num}"
            
            try:
                self.graph_service.execute_query("""
                    MATCH (s:Statute {id: $statute_id})
                    MERGE (c:Chapter {id: $chapter_id})
                    SET c.number = $number,
                        c.title = $title,
                        c.statute_id = $statute_id,
                        c.statute_type = 'bare_act'
                    MERGE (s)-[:HAS_CHAPTER]->(c)
                """, {
                    "statute_id": statute_id,
                    "chapter_id": chapter_id,
                    "number": ch_num,
                    "title": ch_title
                })
                
                chapter_ids[ch_num] = chapter_id
                self.stats["chapters_created"] += 1
                
            except Exception as e:
                logger.warning(f"Failed to create chapter {ch_num}: {e}")
                self.stats["warnings"].append(f"Chapter creation failed: {ch_num}")
        
        logger.info(f"Created {len(chapter_ids)} chapters for {statute_id}")
        return chapter_ids
    
    def _create_section_nodes(self, act_data: Dict[str, Any], statute_id: str, 
                              chapter_ids: Dict[str, str]) -> List[Dict[str, Any]]:
        """Create Section nodes and prepare chunks for embedding."""
        chunks_to_embed = []
        sections_created = 0
        
        for section in act_data.get("sections", []):
            sec_num = section.get("number", "")
            sec_title = section.get("title", "")
            sec_content = section.get("content", "")
            ch_num = section.get("chapter_number", "")
            ch_title = section.get("chapter_title", "")
            
            if not sec_num:
                continue
            
            section_id = f"{statute_id}_section_{sec_num}"
            chapter_id = chapter_ids.get(ch_num, "")
            
            try:
                # Create section node
                self.graph_service.execute_query("""
                    MATCH (s:Statute {id: $statute_id})
                    MERGE (sec:Section {id: $section_id})
                    SET sec.number = $number,
                        sec.title = $title,
                        sec.content = $content,
                        sec.chapter_number = $chapter_number,
                        sec.chapter_title = $chapter_title,
                        sec.has_proviso = $has_proviso,
                        sec.has_explanation = $has_explanation,
                        sec.statute_id = $statute_id,
                        sec.statute_type = 'bare_act'
                    MERGE (s)-[:HAS_SECTION]->(sec)
                """, {
                    "statute_id": statute_id,
                    "section_id": section_id,
                    "number": sec_num,
                    "title": sec_title,
                    "content": (sec_content or "")[:5000],
                    "chapter_number": ch_num,
                    "chapter_title": ch_title,
                    "has_proviso": section.get("has_proviso", False),
                    "has_explanation": section.get("has_explanation", False)
                })
                
                # Link to chapter if available
                if chapter_id:
                    self.graph_service.execute_query("""
                        MATCH (c:Chapter {id: $chapter_id})
                        MATCH (sec:Section {id: $section_id})
                        MERGE (c)-[:CONTAINS_SECTION]->(sec)
                    """, {
                        "chapter_id": chapter_id,
                        "section_id": section_id
                    })
                
                sections_created += 1
                self.stats["sections_created"] += 1
                
                # Prepare chunk for embedding
                chunk_text = f"Section {sec_num}: {sec_title}"
                if sec_content:
                    chunk_text += f"\n\n{sec_content}"
                
                if len(chunk_text.strip()) > 20:
                    chunks_to_embed.append({
                        "section_id": section_id,
                        "section_number": sec_num,
                        "section_title": sec_title,
                        "chapter_number": ch_num,
                        "chapter_title": ch_title,
                        "statute_name": act_data.get("name", ""),
                        "statute_year": act_data.get("year", 0),
                        "text": chunk_text[:4000]
                    })
                    
            except Exception as e:
                logger.warning(f"Failed to create section {sec_num}: {e}")
                self.stats["warnings"].append(f"Section creation failed: {sec_num}")
        
        logger.info(f"Created {sections_created} sections for {statute_id}")
        return chunks_to_embed
    
    def _generate_embeddings_batch(self, texts: List[str], batch_size: int = 50) -> List[List[float]]:
        """Generate embeddings in batches with error handling."""
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            
            for attempt in range(MAX_RETRIES):
                try:
                    embeddings = embedding_client.generate_embeddings(batch_texts)
                    all_embeddings.extend(embeddings)
                    self.stats["embeddings_generated"] += len(embeddings)
                    logger.info(f"Embedded batch {i // batch_size + 1}/{(len(texts) - 1) // batch_size + 1}")
                    break
                    
                except Exception as e:
                    if attempt < MAX_RETRIES - 1:
                        logger.warning(f"Embedding batch failed (attempt {attempt + 1}): {e}")
                        time.sleep(RETRY_DELAY)
                    else:
                        logger.error(f"Embedding batch failed after {MAX_RETRIES} attempts: {e}")
                        # Use zero vectors as fallback
                        zero_vector = [0.0] * Config.embedding.VECTOR_SIZE
                        all_embeddings.extend([zero_vector] * len(batch_texts))
                        self.stats["warnings"].append(f"Used zero vectors for {len(batch_texts)} chunks")
        
        return all_embeddings
    
    def _generate_embeddings_and_index_chunks(self, chunks_data: List[Dict[str, Any]], 
                                               act_data: Dict[str, Any]) -> bool:
        """Generate embeddings and index chunks for RAG."""
        if not chunks_data:
            logger.warning("No chunks to embed")
            return True
        
        logger.info(f"Generating embeddings for {len(chunks_data)} chunks...")
        
        # Extract texts for embedding
        texts = [chunk["text"] for chunk in chunks_data]
        
        # Generate embeddings
        all_embeddings = self._generate_embeddings_batch(texts)
        
        if len(all_embeddings) != len(chunks_data):
            logger.error(f"Embedding count mismatch: got {len(all_embeddings)}, expected {len(chunks_data)}")
            return False
        
        # Create HierarchicalChunk objects
        hierarchical_chunks = []
        file_id = self._generate_file_id(act_data)
        
        for idx, (chunk_data, embedding) in enumerate(zip(chunks_data, all_embeddings)):
            chunk_id = f"{file_id}_chunk_{idx}"
            
            chunk = HierarchicalChunk(
                chunk_id=chunk_id,
                document_id=file_id,
                text=chunk_data["text"],
                chunk_metadata=ChunkMetadata(
                    chunk_type=ChunkType.SECTION,
                    topic_id=chunk_data["section_id"],
                    key_terms=[chunk_data["section_number"], chunk_data["statute_name"]],
                    has_equations=False,
                    has_diagrams=False
                ),
                topic_metadata=TopicMetadata(
                    chapter_title=chunk_data["chapter_title"],
                    section_title=f"Section {chunk_data['section_number']}: {chunk_data['section_title']}",
                    page_start=None,
                    page_end=None
                )
            )
            hierarchical_chunks.append(chunk)
        
        # Index using neo4j_repository
        try:
            neo4j_repository.index_chunks(
                chunks=hierarchical_chunks,
                embeddings=all_embeddings,
                user_id=USER_ID,
                collection_id=COLLECTION_ID,
                file_id=file_id,
                file_name=act_data.get("_source_file", "bare_act.json"),
                source_type="legal_document",
                content_type=CONTENT_TYPE
            )
            self.stats["chunks_indexed"] += len(hierarchical_chunks)
            logger.info(f"Indexed {len(hierarchical_chunks)} chunks for {act_data['name']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to index chunks: {e}")
            self.stats["errors"].append(f"Index error: {act_data['name']} - {str(e)}")
            return False
    
    def _mark_collection_public(self):
        """Mark collection and chunks as public."""
        try:
            self.graph_service.execute_query("""
                MATCH (c:Collection {collection_id: $collection_id})
                SET c.is_public = true
            """, {"collection_id": COLLECTION_ID})
            
            self.graph_service.execute_query("""
                MATCH (c:Chunk {collection_id: $collection_id})
                SET c.is_public = true
            """, {"collection_id": COLLECTION_ID})
            
            logger.info(f"Marked {COLLECTION_ID} as public")
            
        except Exception as e:
            logger.warning(f"Failed to mark public: {e}")
    
    def process_single_act(self, act_data: Dict[str, Any], clean_first: bool = True) -> bool:
        """Process a single act with full error handling."""
        act_name = act_data.get('name', 'Unknown')
        
        try:
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing: {act_name}")
            logger.info(f"{'='*60}")
            
            # Skip acts with no sections
            if not act_data.get("sections"):
                logger.warning(f"Skipping {act_name} - no sections")
                self.stats["skipped"].append(f"{act_name} (no sections)")
                return False
            
            # Generate IDs
            statute_id = self._generate_statute_id(act_data)
            file_id = self._generate_file_id(act_data)
            
            # Clean existing data if requested
            if clean_first:
                self._clean_statute_data(statute_id, file_id)
            
            # Create statute node
            if not self._create_statute_node(act_data, statute_id):
                return False
            
            # Create chapter nodes
            chapter_ids = self._create_chapter_nodes(act_data, statute_id)
            
            # Create section nodes and prepare chunks
            chunks_to_embed = self._create_section_nodes(act_data, statute_id, chapter_ids)
            
            # Generate embeddings and index chunks
            if not self._generate_embeddings_and_index_chunks(chunks_to_embed, act_data):
                return False
            
            self.stats["acts_processed"] += 1
            logger.info(f"✅ Successfully processed: {act_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to process {act_name}: {e}")
            logger.debug(traceback.format_exc())
            self.stats["errors"].append(f"Process error: {act_name} - {str(e)}")
            return False
    
    def run_ingestion(self, clean_first: bool = True) -> Dict[str, Any]:
        """Run the full ingestion pipeline."""
        logger.info("=" * 60)
        logger.info("Starting Bare Acts Ingestion Pipeline")
        logger.info("=" * 60)
        
        # Initialize
        if not self._init_services():
            return self.stats
        
        # Load parsed JSON files
        parsed_acts = self._load_json_files()
        if not parsed_acts:
            logger.error("No parsed acts found!")
            return self.stats
        
        # Create collection
        try:
            self._create_collection()
        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            self.stats["errors"].append(f"Collection creation failed: {str(e)}")
            return self.stats
        
        # Process each act
        for act_data in parsed_acts:
            self.process_single_act(act_data, clean_first)
        
        # Mark collection as public
        self._mark_collection_public()
        
        # Log final stats
        self._print_stats()
        
        return self.stats
    
    def _print_stats(self):
        """Print final statistics."""
        logger.info("\n" + "=" * 60)
        logger.info("Ingestion Complete!")
        logger.info("=" * 60)
        print(f"Acts processed: {self.stats['acts_processed']}")
        print(f"Chapters created: {self.stats['chapters_created']}")
        print(f"Sections created: {self.stats['sections_created']}")
        print(f"Chunks indexed: {self.stats['chunks_indexed']}")
        print(f"Embeddings generated: {self.stats['embeddings_generated']}")
        
        if self.stats["skipped"]:
            logger.warning(f"Skipped: {len(self.stats['skipped'])}")
            for s in self.stats["skipped"]:
                logger.warning(f"  - {s}")
        
        if self.stats["warnings"]:
            logger.warning(f"Warnings: {len(self.stats['warnings'])}")
        
        if self.stats["errors"]:
            logger.error(f"Errors: {len(self.stats['errors'])}")
            for err in self.stats["errors"]:
                logger.error(f"  - {err}")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Ingest bare acts into Neo4j")
    parser.add_argument("--parsed-dir", default="output", 
                        help="Directory containing parsed JSON files")
    parser.add_argument("--json-file", help="Path to a single parsed JSON file")
    parser.add_argument("--no-clean", action="store_true",
                        help="Don't clean existing data before ingestion")
    parser.add_argument("--dry-run", action="store_true",
                        help="Only validate, don't actually ingest")
    
    args = parser.parse_args()
    
    runner = BareActsIngestionRunner(args.parsed_dir)
    
    if args.dry_run:
        logger.info("DRY RUN MODE - Validating only")
        acts = runner._load_json_files()
        total_sections = sum(a.get("total_sections", 0) for a in acts)
        total_chapters = sum(a.get("total_chapters", 0) for a in acts)
        logger.info(f"Would process {len(acts)} acts, {total_chapters} chapters, {total_sections} sections")
        return 0
    
    # Initialize services first
    if not runner._init_services():
        logger.error("Failed to initialize services")
        return 1
    
    # Create collection
    try:
        runner._create_collection()
    except Exception as e:
        logger.error(f"Failed to create collection: {e}")
        return 1
    
    # Load act(s)
    if args.json_file:
        logger.info(f"Processing single file: {args.json_file}")
        act_data = runner._load_json_file(Path(args.json_file))
        if not act_data:
            logger.error("Failed to load JSON file")
            return 1
        parsed_acts = [act_data]
    else:
        parsed_acts = runner._load_json_files()

    if not parsed_acts:
        logger.error("No parsed acts found!")
        return 1

    # Process each act
    for act_data in parsed_acts:
        runner.process_single_act(act_data, clean_first=not args.no_clean)

    runner._mark_collection_public()
    runner._print_stats()
    
    return 0 if not runner.stats["errors"] else 1


if __name__ == "__main__":
    exit(main())
