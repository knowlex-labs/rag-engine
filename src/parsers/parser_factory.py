"""
Factory for creating appropriate parser based on source type.
"""

import logging
from typing import Union, Optional
from pathlib import Path
from urllib.parse import urlparse

from .base_parser import BaseParser
from .pdf_parser import PDFParser
from .youtube_parser import YouTubeParser
from .web_parser import WebParser

logger = logging.getLogger(__name__)


class ParserFactory:
    """
    Factory class to create appropriate parser based on source type.

    Usage:
        # Explicit source type
        parser = ParserFactory.get_parser("pdf")

        # Auto-detect from source
        parser = ParserFactory.create_parser_for_source("https://youtube.com/watch?v=...")
    """

    @staticmethod
    def get_parser(source_type: str, **kwargs) -> BaseParser:
        """
        Get parser for specific source type.

        Args:
            source_type: Type of source ('pdf', 'youtube', 'web')
            **kwargs: Additional configuration for parser
                - gemini_api_key: Required for YouTubeParser
                - user_agent: Optional for WebParser
                - timeout: Optional for WebParser and YouTubeParser

        Returns:
            Appropriate parser instance

        Raises:
            ValueError: If source_type is not supported
        """
        source_type = source_type.lower()

        if source_type == "pdf":
            return PDFParser()

        elif source_type == "youtube":
            gemini_api_key = kwargs.get('gemini_api_key')
            if not gemini_api_key:
                raise ValueError("gemini_api_key is required for YouTube parser")

            timeout = kwargs.get('timeout', 60)
            return YouTubeParser(
                gemini_api_key=gemini_api_key,
                timeout=timeout
            )

        elif source_type == "web":
            user_agent = kwargs.get('user_agent', 'RAG-Engine/1.0')
            timeout = kwargs.get('timeout', 30)
            return WebParser(
                user_agent=user_agent,
                timeout=timeout
            )

        else:
            raise ValueError(
                f"Unsupported source type: {source_type}. "
                f"Supported types: pdf, youtube, web"
            )

    @staticmethod
    def create_parser_for_source(
        source: Union[str, Path],
        **kwargs
    ) -> BaseParser:
        """
        Auto-detect source type and create appropriate parser.

        Args:
            source: File path, YouTube URL, or web URL
            **kwargs: Additional configuration passed to parser

        Returns:
            Appropriate parser instance

        Raises:
            ValueError: If source type cannot be determined
        """
        source_type = ParserFactory.detect_source_type(source)
        logger.info(f"Detected source type: {source_type} for source: {source}")
        return ParserFactory.get_parser(source_type, **kwargs)

    @staticmethod
    def detect_source_type(source: Union[str, Path]) -> str:
        """
        Detect source type from source identifier.

        Args:
            source: File path, YouTube URL, or web URL

        Returns:
            Source type: 'pdf', 'youtube', or 'web'

        Raises:
            ValueError: If source type cannot be determined
        """
        # File path
        if isinstance(source, Path):
            if source.suffix.lower() == '.pdf':
                return 'pdf'
            else:
                raise ValueError(f"Unsupported file type: {source.suffix}")

        source_str = str(source)

        # Try parsing as URL
        try:
            parsed = urlparse(source_str)

            # Not a URL (no scheme)
            if not parsed.scheme:
                # Assume it's a file path
                path = Path(source_str)
                if path.suffix.lower() == '.pdf':
                    return 'pdf'
                else:
                    raise ValueError(f"Unsupported file type: {path.suffix}")

            # YouTube URL
            if ParserFactory._is_youtube_url(parsed):
                return 'youtube'

            # Web URL
            if parsed.scheme in ['http', 'https']:
                return 'web'

            raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")

        except Exception as e:
            raise ValueError(f"Cannot determine source type for: {source}. Error: {e}")

    @staticmethod
    def _is_youtube_url(parsed_url) -> bool:
        """Check if URL is a YouTube URL."""
        youtube_domains = [
            'youtube.com',
            'www.youtube.com',
            'youtu.be',
            'm.youtube.com'
        ]
        return parsed_url.netloc in youtube_domains

    @staticmethod
    def get_available_parsers() -> dict:
        """
        Get information about available parsers.

        Returns:
            Dictionary with parser information
        """
        return {
            'pdf': {
                'class': 'PDFParser',
                'description': 'Parses PDF documents with hierarchical structure detection',
                'supports': ['.pdf'],
                'required_params': []
            },
            'youtube': {
                'class': 'YouTubeParser',
                'description': 'Transcribes YouTube videos with timestamp sections',
                'supports': ['youtube.com', 'youtu.be'],
                'required_params': ['gemini_api_key']
            },
            'web': {
                'class': 'WebParser',
                'description': 'Scrapes web articles (static HTML only)',
                'supports': ['http://', 'https://'],
                'required_params': []
            }
        }
