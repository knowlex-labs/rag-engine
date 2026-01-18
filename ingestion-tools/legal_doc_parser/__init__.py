"""
Legal Document Parser
A flexible parser for legal documents that extracts hierarchical structure,
entities, and relationships for Neo4j graph indexing.
"""

__version__ = "0.1.0"

from .document_parser import LegalDocumentParser
from .structure_parser import DocumentStructureParser
from .entity_parser import EntityParser
from .validation import ParsingValidator
from .llm_extractor import LLMLegalExtractor

__all__ = [
    "LegalDocumentParser",
    "DocumentStructureParser",
    "EntityParser",
    "ParsingValidator",
    "LLMLegalExtractor"
]