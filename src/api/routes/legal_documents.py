"""
API routes for legal document ingestion (Constitution, BNS, etc.)
Following the legal ontology approach.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Header, UploadFile, File, Form
from typing import Optional, List
import shutil
import uuid
import os
import logging
from pathlib import Path

from pydantic import BaseModel
from services.constitution_ingestion_service import constitution_ingestion_service

router = APIRouter()
logger = logging.getLogger(__name__)


class ConstitutionIngestionRequest(BaseModel):
    """Request model for Constitution ingestion."""
    file_path: str
    user_id: Optional[str] = "system"


class ConstitutionIngestionResponse(BaseModel):
    """Response model for Constitution ingestion."""
    status: str
    constitution_id: Optional[str] = None
    message: str
    statistics: Optional[dict] = None
    errors: List[str] = []


class LegalDocumentStatus(BaseModel):
    """Status model for legal documents."""
    document_type: str
    document_name: str
    status: str
    provisions_count: int
    indexed_at: Optional[str] = None


@router.post("/api/v1/legal-documents/constitution/ingest", response_model=ConstitutionIngestionResponse)
async def ingest_constitution(
    request: ConstitutionIngestionRequest,
    background_tasks: BackgroundTasks,
    x_user_id: str = Header(default="system")
):
    """
    Ingest Constitution of India into the knowledge graph.
    This creates the golden source constitutional data following legal ontology.
    """
    try:
        logger.info(f"Constitution ingestion requested by user {x_user_id}")
        logger.info(f"File path: {request.file_path}")

        # Validate file exists
        if not os.path.exists(request.file_path):
            raise HTTPException(
                status_code=400,
                detail=f"File not found: {request.file_path}"
            )

        # Validate it's a PDF
        if not request.file_path.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=400,
                detail="Constitution file must be a PDF"
            )

        # Use system user for golden source documents
        user_id = request.user_id or "system"

        # Run ingestion (this will take several minutes)
        logger.info("Starting Constitution ingestion process...")
        result = await constitution_ingestion_service.ingest_constitution(
            request.file_path,
            user_id
        )

        if result["status"] == "success":
            return ConstitutionIngestionResponse(
                status="success",
                constitution_id=result["constitution_id"],
                message="Constitution ingested successfully",
                statistics=result["statistics"]
            )
        elif result["status"] == "already_indexed":
            return ConstitutionIngestionResponse(
                status="already_indexed",
                constitution_id=result.get("constitution_id"),
                message="Constitution already indexed in the system"
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Ingestion failed with status: {result['status']}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Constitution ingestion failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error during Constitution ingestion: {str(e)}"
        )


@router.post("/api/v1/legal-documents/constitution/upload", response_model=ConstitutionIngestionResponse)
async def upload_and_ingest_constitution(
    file: UploadFile = File(...),
    user_id: str = Form(default="system"),
    x_user_id: str = Header(default="system")
):
    """
    Upload Constitution PDF and ingest it into the knowledge graph.
    """
    try:
        logger.info(f"Constitution upload and ingestion requested by user {x_user_id}")

        # Validate file type
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=400,
                detail="Constitution file must be a PDF"
            )

        # Create upload directory
        upload_dir = Path("uploads/constitution")
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Save uploaded file
        file_path = upload_dir / f"constitution_{uuid.uuid4()}.pdf"
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        logger.info(f"Constitution file saved to: {file_path}")

        # Ingest the uploaded file
        result = await constitution_ingestion_service.ingest_constitution(
            str(file_path),
            user_id
        )

        # Clean up uploaded file after ingestion
        try:
            os.remove(file_path)
        except:
            logger.warning(f"Could not clean up uploaded file: {file_path}")

        if result["status"] == "success":
            return ConstitutionIngestionResponse(
                status="success",
                constitution_id=result["constitution_id"],
                message="Constitution uploaded and ingested successfully",
                statistics=result["statistics"]
            )
        elif result["status"] == "already_indexed":
            return ConstitutionIngestionResponse(
                status="already_indexed",
                constitution_id=result.get("constitution_id"),
                message="Constitution already indexed in the system"
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Ingestion failed with status: {result['status']}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Constitution upload and ingestion failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/api/v1/legal-documents/status", response_model=List[LegalDocumentStatus])
async def get_legal_documents_status(x_user_id: str = Header(default="system")):
    """
    Get status of all legal documents in the system.
    """
    try:
        from services.graph_service import get_graph_service

        graph_service = get_graph_service()

        # Get all Statute nodes (legal documents)
        query = """
        MATCH (s:Statute)
        OPTIONAL MATCH (s)-[:HAS_PROVISION]->(p:Provision)
        RETURN s.name as document_name,
               s.type as document_type,
               s.indexed_at as indexed_at,
               count(p) as provisions_count
        ORDER BY s.name
        """

        results = graph_service.execute_query(query)

        documents = []
        for result in results:
            documents.append(LegalDocumentStatus(
                document_type=result['document_type'] or "UNKNOWN",
                document_name=result['document_name'],
                status="indexed" if result['provisions_count'] > 0 else "empty",
                provisions_count=result['provisions_count'] or 0,
                indexed_at=result['indexed_at']
            ))

        return documents

    except Exception as e:
        logger.error(f"Error getting legal documents status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving legal documents status: {str(e)}"
        )


@router.get("/api/v1/legal-documents/constitution/structure")
async def get_constitution_structure(x_user_id: str = Header(default="system")):
    """
    Get the hierarchical structure of the Constitution.
    Useful for debugging and verification.
    """
    try:
        from services.graph_service import get_graph_service

        graph_service = get_graph_service()

        # Get Constitution structure
        structure_query = """
        MATCH (s:Statute {name: "Constitution of India"})
        OPTIONAL MATCH (s)-[:HAS_PART]->(part:Part)
        OPTIONAL MATCH (part)-[:CONTAINS]->(provision:Provision {provision_type: "ARTICLE"})
        RETURN s.name as constitution,
               collect(DISTINCT {
                   part_number: part.number,
                   part_title: part.title,
                   article_count: size([p IN collect(provision) WHERE p IS NOT NULL])
               }) as parts
        """

        result = graph_service.execute_query(structure_query)

        if not result:
            raise HTTPException(
                status_code=404,
                detail="Constitution not found in the system"
            )

        # Get summary statistics
        stats_query = """
        MATCH (s:Statute {name: "Constitution of India"})
        OPTIONAL MATCH (s)-[:HAS_PROVISION]->(article:Provision {provision_type: "ARTICLE"})
        OPTIONAL MATCH (s)-[:HAS_SCHEDULE]->(schedule:Provision {provision_type: "SCHEDULE"})
        OPTIONAL MATCH (s)-[:HAS_PART]->(part:Part)
        RETURN count(DISTINCT article) as articles_count,
               count(DISTINCT schedule) as schedules_count,
               count(DISTINCT part) as parts_count
        """

        stats_result = graph_service.execute_query(stats_query)

        return {
            "constitution": result[0]["constitution"],
            "structure": {
                "parts": result[0]["parts"],
                "statistics": stats_result[0] if stats_result else {}
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Constitution structure: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving Constitution structure: {str(e)}"
        )


@router.get("/api/v1/legal-documents/constitution/articles/{article_number}")
async def get_constitutional_article(
    article_number: str,
    x_user_id: str = Header(default="system")
):
    """
    Get a specific constitutional article by number.
    Example: /api/v1/legal-documents/constitution/articles/21
    """
    try:
        from services.graph_service import get_graph_service

        graph_service = get_graph_service()

        # Get specific article
        query = """
        MATCH (article:Provision {provision_type: "ARTICLE", number: $article_number})
        WHERE article.statute_name = "Constitution of India"
        OPTIONAL MATCH (article)-[:REFERENCES]->(ref:Provision)
        RETURN article.id as id,
               article.number as number,
               article.title as title,
               article.text as text,
               article.part as part,
               collect(ref.id) as references
        """

        result = graph_service.execute_query(query, {"article_number": article_number})

        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Article {article_number} not found"
            )

        article = result[0]

        # Get related legal concepts
        concept_query = """
        MATCH (article:Provision {id: $article_id})<-[:DERIVED_FROM]-(concept:LegalConcept)
        RETURN collect(concept.name) as legal_concepts
        """

        concept_result = graph_service.execute_query(concept_query, {"article_id": article["id"]})

        return {
            "article": {
                "id": article["id"],
                "number": article["number"],
                "title": article["title"],
                "text": article["text"],
                "part": article["part"],
                "references": [ref for ref in article["references"] if ref],
                "legal_concepts": concept_result[0]["legal_concepts"] if concept_result else []
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Article {article_number}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving Article {article_number}: {str(e)}"
        )