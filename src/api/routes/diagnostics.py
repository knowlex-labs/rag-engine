"""
Diagnostic endpoint to check Neo4j configuration without exposing secrets
"""
from fastapi import APIRouter
from typing import Dict, Any
import os
from config import Config

router = APIRouter()

@router.get("/api/v1/diagnostics/neo4j")
async def neo4j_diagnostics() -> Dict[str, Any]:
    """Check Neo4j configuration status"""
    
    return {
        "neo4j_uri": Config.neo4j.URI,
        "neo4j_user": Config.neo4j.USER,
        "neo4j_password_set": bool(Config.neo4j.PASSWORD),
        "neo4j_password_length": len(Config.neo4j.PASSWORD) if Config.neo4j.PASSWORD else 0,
        "neo4j_database": Config.neo4j.DATABASE,
        "neo4j_vector_index": Config.neo4j.VECTOR_INDEX_NAME,
        "env_vars_present": {
            "NEO4J_URI": bool(os.getenv("NEO4J_URI")),
            "NEO4J_USER": bool(os.getenv("NEO4J_USER")),
            "NEO4J_PASSWORD": bool(os.getenv("NEO4J_PASSWORD")),
            "NEO4J_DATABASE": bool(os.getenv("NEO4J_DATABASE"))
        }
    }

@router.get("/api/v1/diagnostics/connection-test")
async def test_neo4j_connection() -> Dict[str, Any]:
    """Test actual Neo4j connection with detailed debugging"""
    from services.graph_service import get_graph_service
    import traceback

    debug_info = {
        "uri": Config.neo4j.URI,
        "user": Config.neo4j.USER,
        "database": Config.neo4j.DATABASE,
        "password_set": bool(Config.neo4j.PASSWORD),
        "is_auradb": "neo4j.io" in Config.neo4j.URI,
        "protocol": Config.neo4j.URI.split("://")[0] if "://" in Config.neo4j.URI else "unknown"
    }

    try:
        graph_service = get_graph_service()

        # Test basic connection
        result = graph_service.execute_query("RETURN 1 as test")

        # Test database info query
        db_info = graph_service.execute_query("CALL dbms.components() YIELD name, versions, edition")

        return {
            "status": "connected",
            "test_query_result": result[0]["test"] if result else None,
            "database_info": [dict(record) for record in db_info] if db_info else None,
            "debug_info": debug_info,
            "message": "Successfully connected to Neo4j"
        }
    except Exception as e:
        return {
            "status": "failed",
            "error_type": type(e).__name__,
            "error_message": str(e),
            "error_traceback": traceback.format_exc(),
            "debug_info": debug_info,
            "message": "Failed to connect to Neo4j"
        }
