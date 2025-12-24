
import logging
from typing import Union
from pathlib import Path
from urllib.parse import urlparse

from .base_parser import BaseParser
from .pdf_parser import PDFParser
from .youtube_parser import YouTubeParser
from .web_parser import WebParser
from .constitution_parser import ConstitutionParser
from config import Config

logger = logging.getLogger(__name__)

class ParserFactory:
    @staticmethod
    def get_parser(source_type: str, **kwargs) -> BaseParser:
        source_type = source_type.lower()

        if source_type == "pdf":
            return PDFParser()

        elif source_type == "file":
            # For file content type, we need to detect the actual file format
            # This will be called with the downloaded file path, so we can detect from extension
            return PDFParser()  # Default to PDF for now, could be enhanced to detect format

        elif source_type == "youtube":
            return YouTubeParser(
                gemini_api_key=Config.llm.GEMINI_API_KEY
            )

        elif source_type == "web":
            user_agent = kwargs.get('user_agent', 'RAG-Engine/1.0')
            timeout = kwargs.get('timeout', 30)
            return WebParser(
                user_agent=user_agent,
                timeout=timeout
            )

        elif source_type == "constitution":
            return ConstitutionParser()

        else:
            raise ValueError(f"Unsupported source type: {source_type}")

    @staticmethod
    def create_parser_for_source(source: Union[str, Path], **kwargs) -> BaseParser:
        source_type = ParserFactory.detect_source_type(source)
        logger.info(f"Detected source type: {source_type} for source: {source}")
        return ParserFactory.get_parser(source_type, **kwargs)

    @staticmethod
    def detect_source_type(source: Union[str, Path]) -> str:
        if isinstance(source, Path):
            if source.suffix.lower() == '.pdf':
                # Check if this is a Constitution document
                source_name = source.name.lower()
                if ParserFactory._is_constitution_document(source_name):
                    return 'constitution'
                return 'pdf'
            else:
                raise ValueError(f"Unsupported file type: {source.suffix}")

        source_str = str(source)

        try:
            parsed = urlparse(source_str)

            if not parsed.scheme:
                path = Path(source_str)
                if path.suffix.lower() == '.pdf':
                    # Check if this is a Constitution document
                    if ParserFactory._is_constitution_document(source_str.lower()):
                        return 'constitution'
                    return 'pdf'
                else:
                    raise ValueError(f"Unsupported file type: {path.suffix}")

            if ParserFactory._is_youtube_url(parsed):
                return 'youtube'

            if parsed.scheme in ['http', 'https']:
                return 'web'

            raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")

        except Exception as e:
            raise ValueError(f"Cannot determine source type for: {source}. Error: {e}")

    @staticmethod
    def _is_youtube_url(parsed_url) -> bool:
        youtube_domains = [
            'youtube.com',
            'www.youtube.com',
            'youtu.be',
            'm.youtube.com'
        ]
        return parsed_url.netloc in youtube_domains

    @staticmethod
    def _is_constitution_document(filename: str) -> bool:
        """Check if filename indicates this is a Constitution document."""
        constitution_indicators = [
            "constitution", "constitutional", "bharatiya", "संविधान", "samvidhan",
            "fundamental_rights", "directive_principles", "emergency_provisions"
        ]
        return any(indicator in filename for indicator in constitution_indicators)

    @staticmethod
    def get_available_parsers() -> dict:
        return {
            'pdf': {
                'class': 'PDFParser',
                'description': 'Parses PDF documents',
                'supports': ['.pdf'],
                'required_params': []
            },
            'constitution': {
                'class': 'ConstitutionParser',
                'description': 'Parses Constitution of India with hierarchical structure extraction',
                'supports': ['constitution.pdf', 'constitutional documents'],
                'required_params': []
            },
            'youtube': {
                'class': 'YouTubeParser',
                'description': 'Transcribes YouTube videos',
                'supports': ['youtube.com', 'youtu.be'],
                'required_params': []
            },
            'web': {
                'class': 'WebParser',
                'description': 'Scrapes web articles',
                'supports': ['http://', 'https://'],
                'required_params': []
            }
        }
