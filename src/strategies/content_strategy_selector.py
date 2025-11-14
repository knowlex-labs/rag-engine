"""
Content strategy selector - auto-detects content type and selects chunking strategy.

Uses first-page analysis to determine if content is a BOOK, CHAPTER, or DOCUMENT.
"""

import re
import logging
from typing import Optional
import pdfplumber
from strategies.base_chunking_strategy import BaseChunkingStrategy
from strategies.book_chunking_strategy import BookChunkingStrategy
from strategies.chapter_chunking_strategy import ChapterChunkingStrategy
from strategies.document_chunking_strategy import DocumentChunkingStrategy
from models.api_models import ContentType

logger = logging.getLogger(__name__)


class ContentStrategySelector:
    """
    Intelligent content type detection and strategy selection.

    Detection strategy:
    1. If user provides explicit hint (not AUTO), use it
    2. Otherwise, read first page and analyze:
       - Book indicators: Edition, ISBN, Copyright, TOC with multiple chapters
       - Chapter indicators: "Chapter N" at start, chapter numbering
       - Default: Document (for small files or unclear content)
    """

    def __init__(self):
        """Initialize with all available strategies."""
        self.strategies = {
            ContentType.BOOK: BookChunkingStrategy(),
            ContentType.CHAPTER: ChapterChunkingStrategy(),
            ContentType.DOCUMENT: DocumentChunkingStrategy()
        }

    def detect_content_type(
        self,
        file_path: str,
        user_hint: Optional[ContentType] = None
    ) -> ContentType:
        """
        Detect content type by analyzing first page.

        Args:
            file_path: Path to the PDF file
            user_hint: Optional user-provided content type hint

        Returns:
            Detected or user-specified ContentType
        """
        # If user explicitly specified type (not AUTO), use it
        if user_hint and user_hint != ContentType.AUTO:
            logger.info(f"Using user-specified content type: {user_hint.value}")
            return user_hint

        # Auto-detect by reading first page
        try:
            first_page_text = self._read_first_page(file_path)

            if not first_page_text:
                logger.warning(f"Could not read first page from {file_path}, defaulting to DOCUMENT")
                return ContentType.DOCUMENT

            # Check for book indicators
            if self._is_book_first_page(first_page_text):
                logger.info(f"Detected BOOK content type from first page analysis")
                return ContentType.BOOK

            # Check for chapter indicators
            if self._is_chapter_first_page(first_page_text):
                logger.info(f"Detected CHAPTER content type from first page analysis")
                return ContentType.CHAPTER

            # Default to document for small or unclear content
            logger.info(f"No clear indicators found, defaulting to DOCUMENT content type")
            return ContentType.DOCUMENT

        except Exception as e:
            logger.error(f"Error detecting content type from {file_path}: {e}")
            logger.info("Defaulting to DOCUMENT strategy")
            return ContentType.DOCUMENT

    def get_strategy(self, content_type: ContentType) -> BaseChunkingStrategy:
        """
        Get the appropriate chunking strategy for a content type.

        Args:
            content_type: The type of content to process

        Returns:
            Appropriate strategy instance

        Raises:
            ValueError: If content_type is invalid
        """
        if content_type == ContentType.AUTO:
            # This shouldn't happen if detect_content_type is called first
            logger.warning("AUTO type passed to get_strategy, defaulting to DOCUMENT")
            return self.strategies[ContentType.DOCUMENT]

        strategy = self.strategies.get(content_type)
        if not strategy:
            logger.error(f"No strategy found for content type: {content_type}")
            return self.strategies[ContentType.DOCUMENT]

        logger.info(f"Selected strategy: {strategy}")
        return strategy

    def _read_first_page(self, file_path: str) -> Optional[str]:
        """
        Read and extract text from the first page of a PDF.

        Args:
            file_path: Path to the PDF file

        Returns:
            Text content of first page, or None if failed
        """
        try:
            with pdfplumber.open(file_path) as pdf:
                if len(pdf.pages) == 0:
                    return None

                first_page = pdf.pages[0]
                text = first_page.extract_text()

                return text if text else None

        except Exception as e:
            logger.error(f"Failed to read first page from {file_path}: {e}")
            return None

    def _is_book_first_page(self, text: str) -> bool:
        """
        Detect if first page is a book title page.

        Indicators:
        - Contains "edition" (e.g., "11th Edition")
        - Contains "ISBN" followed by number
        - Contains "Copyright" or "Published"
        - Contains table of contents with 3+ chapter references
        - Contains "Press" or "Publisher"

        Args:
            text: First page text

        Returns:
            True if indicators suggest this is a book
        """
        text_lower = text.lower()

        # Strong indicators
        strong_indicators = [
            r'\bedition\b',                     # "11th Edition"
            r'\bisbn[\s\-:]*\d',               # "ISBN: 978..."
            r'\bcopyright\s+©?\s*\d{4}',       # "Copyright 2020"
            r'\bpublished\s+by\b',             # "Published by..."
            r'\b(?:university|academic)\s+press\b'  # "Oxford University Press"
        ]

        strong_match_count = 0
        for pattern in strong_indicators:
            if re.search(pattern, text_lower):
                strong_match_count += 1
                logger.debug(f"Found book indicator: {pattern}")

        # If 2+ strong indicators, likely a book
        if strong_match_count >= 2:
            return True

        # Check for table of contents with multiple chapters
        chapter_pattern = r'chapter\s+\d+'
        chapter_matches = re.findall(chapter_pattern, text_lower)

        if len(chapter_matches) >= 3:
            logger.debug(f"Found {len(chapter_matches)} chapter references in TOC")
            return True

        return False

    def _is_chapter_first_page(self, text: str) -> bool:
        """
        Detect if first page is a chapter start page.

        Indicators:
        - Starts with "Chapter N" (where N is a number)
        - Starts with "N." followed by title
        - Contains "CHAPTER N" in large text at top
        - Early in text (within first 5 lines)

        Args:
            text: First page text

        Returns:
            True if indicators suggest this is a chapter
        """
        lines = text.split('\n')

        # Check first 5 lines for chapter indicators
        first_lines = '\n'.join(lines[:5])

        chapter_patterns = [
            r'^chapter\s+\d+',              # "Chapter 5"
            r'^ch\.?\s*\d+',                # "Ch. 5" or "Ch 5"
            r'^\d+\.\s+[A-Z]',              # "5. Force and Motion"
            r'^CHAPTER\s+\d+',              # "CHAPTER 5" (all caps)
        ]

        for pattern in chapter_patterns:
            if re.search(pattern, first_lines, re.IGNORECASE | re.MULTILINE):
                logger.debug(f"Found chapter indicator: {pattern}")
                return True

        return False
