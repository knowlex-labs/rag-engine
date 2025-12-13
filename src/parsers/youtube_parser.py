"""
YouTube parser with transcript API and Gemini fallback.
"""

import re
import logging
from typing import List, Optional
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from .base_parser import BaseParser
from .models import ParsedContent, ParsedMetadata, ContentSection

logger = logging.getLogger(__name__)


class YouTubeParser(BaseParser):
    """
    YouTube video parser that extracts transcripts.

    Strategy:
    1. Primary: Use youtube-transcript-api (no API key needed)
    2. Fallback: Use Gemini 2.5 Flash to transcribe (if transcript API blocked)

    Features:
    - Extracts timestamp-based segments
    - Preserves video metadata (title, channel, duration)
    - Creates clickable timestamp references
    """

    def __init__(self, gemini_api_key: Optional[str] = None):
        super().__init__()
        self.gemini_api_key = gemini_api_key

        # YouTube URL patterns
        self.youtube_patterns = [
            r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
            r'(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})',
            r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        ]

    def can_handle(self, source: str | Path) -> bool:
        """Check if source is a YouTube URL."""
        if isinstance(source, Path):
            return False

        video_id = self._extract_video_id(source)
        return video_id is not None

    def parse(self, source: str | Path) -> ParsedContent:
        """
        Parse YouTube video and extract transcript.

        Args:
            source: YouTube URL

        Returns:
            ParsedContent with timestamp-based sections

        Raises:
            ValueError: If URL is invalid or transcript unavailable
        """
        if isinstance(source, Path):
            raise ValueError(f"YouTube parser requires a URL, not a file path: {source}")

        self.validate_source(source)

        video_id = self._extract_video_id(source)
        if not video_id:
            raise ValueError(f"Invalid YouTube URL: {source}")

        logger.info(f"Parsing YouTube video: {video_id}")

        # Try to get transcript
        transcript = self._get_transcript(video_id, source)

        # Extract metadata
        metadata = self._extract_metadata(video_id, source)

        # Build full text
        full_text = "\n".join([entry['text'] for entry in transcript])

        # Build timestamp-based sections
        sections = self._build_timestamp_sections(transcript)

        return ParsedContent(
            text=full_text,
            metadata=metadata,
            sections=sections,
            source_type='youtube',
            has_equations=False,  # YouTube transcripts unlikely to have equations
            has_diagrams=False,
            has_code_blocks=False
        )

    def _extract_video_id(self, url: str) -> Optional[str]:
        """Extract YouTube video ID from URL."""
        for pattern in self.youtube_patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        # Try query parameter
        parsed = urlparse(url)
        if 'youtube.com' in parsed.netloc:
            query = parse_qs(parsed.query)
            if 'v' in query:
                return query['v'][0]

        return None

    def _get_transcript(self, video_id: str, url: str) -> List[dict]:
        """
        Get transcript using youtube-transcript-api with Gemini fallback.

        Returns:
            List of transcript entries with format:
            [{'text': '...', 'start': 0.0, 'duration': 2.5}, ...]
        """
        # Try youtube-transcript-api first
        try:
            from youtube_transcript_api import YouTubeTranscriptApi

            logger.info(f"Attempting to fetch transcript via youtube-transcript-api for {video_id}")
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
            logger.info(f"Successfully fetched transcript with {len(transcript)} entries")
            return transcript

        except Exception as e:
            logger.warning(f"youtube-transcript-api failed for {video_id}: {e}")

            # Fallback to Gemini if API key provided
            if self.gemini_api_key:
                logger.info("Falling back to Gemini 2.5 Flash transcription")
                return self._transcribe_with_gemini(url, video_id)
            else:
                raise ValueError(
                    f"Failed to get transcript for {video_id}. "
                    f"youtube-transcript-api failed and no Gemini API key provided for fallback."
                )

    def _transcribe_with_gemini(self, url: str, video_id: str) -> List[dict]:
        """
        Fallback: Use Gemini 2.5 Flash to transcribe YouTube video.

        Note: This is a simplified implementation. In production, you would:
        1. Download the video audio using pytube
        2. Upload to Gemini API for transcription
        3. Parse the response into transcript format
        """
        try:
            from utils.llm_client import LlmClient
            import json

            logger.info(f"Transcribing YouTube video {video_id} with Gemini 2.5 Flash")

            llm_client = LlmClient()

            # Prompt Gemini to transcribe
            prompt = f"""
            Please transcribe the YouTube video at this URL: {url}

            Return the transcription in JSON format with timestamps:
            {{
                "transcript": [
                    {{"text": "segment text", "start": 0.0, "duration": 5.0}},
                    ...
                ]
            }}

            Break the transcript into natural segments (paragraphs or sentences) with approximate timestamps.
            """

            response = llm_client.generate_response(
                query=prompt,
                context="",
                enable_json=True
            )

            # Parse JSON response
            try:
                data = json.loads(response)
                transcript = data.get('transcript', [])

                if not transcript:
                    raise ValueError("Gemini returned empty transcript")

                logger.info(f"Gemini transcription successful: {len(transcript)} segments")
                return transcript

            except json.JSONDecodeError:
                # Fallback: Create single entry if JSON parsing fails
                logger.warning("Failed to parse Gemini JSON response, creating single segment")
                return [{
                    'text': response,
                    'start': 0.0,
                    'duration': 0.0
                }]

        except Exception as e:
            logger.error(f"Gemini transcription failed for {video_id}: {e}")
            raise ValueError(f"All transcription methods failed for {video_id}: {e}")

    def _extract_metadata(self, video_id: str, url: str) -> ParsedMetadata:
        """
        Extract YouTube video metadata.

        Uses pytube to get title, channel, and duration.
        """
        try:
            from pytube import YouTube

            yt = YouTube(url)

            title = yt.title
            channel = yt.author
            duration_seconds = yt.length

            # Convert duration to HH:MM:SS
            hours = duration_seconds // 3600
            minutes = (duration_seconds % 3600) // 60
            seconds = duration_seconds % 60

            if hours > 0:
                duration = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                duration = f"{minutes:02d}:{seconds:02d}"

            return ParsedMetadata(
                title=title,
                url=url,
                duration=duration,
                channel=channel,
                video_id=video_id
            )

        except Exception as e:
            logger.warning(f"Failed to extract metadata for {video_id}: {e}")

            # Return minimal metadata
            return ParsedMetadata(
                title=f"YouTube Video {video_id}",
                url=url,
                duration=None,
                channel=None,
                video_id=video_id
            )

    def _build_timestamp_sections(self, transcript: List[dict]) -> List[ContentSection]:
        """
        Build ContentSection objects from transcript with timestamps.

        Groups transcript entries into larger sections (60-120 seconds each).
        """
        sections = []

        if not transcript:
            return sections

        current_section_text = ""
        current_section_start = 0.0
        section_duration = 0.0
        target_duration = 90.0  # Target ~90 seconds per section

        for entry in transcript:
            text = entry['text']
            start = entry['start']
            duration = entry.get('duration', 0.0)

            if not current_section_text:
                # Start new section
                current_section_start = start
                current_section_text = text
                section_duration = duration
            else:
                # Add to current section
                current_section_text += " " + text
                section_duration += duration

                # If section is long enough, save it
                if section_duration >= target_duration:
                    timestamp = self._format_timestamp(current_section_start)

                    sections.append(ContentSection(
                        level=2,  # All sections are same level
                        text=current_section_text.strip(),
                        title=None,
                        parent_id=None,
                        page_number=None,
                        timestamp=timestamp,
                        section_id=f"timestamp_{timestamp}"
                    ))

                    # Reset for next section
                    current_section_text = ""
                    section_duration = 0.0

        # Add remaining text as final section
        if current_section_text.strip():
            timestamp = self._format_timestamp(current_section_start)

            sections.append(ContentSection(
                level=2,
                text=current_section_text.strip(),
                title=None,
                parent_id=None,
                page_number=None,
                timestamp=timestamp,
                section_id=f"timestamp_{timestamp}"
            ))

        logger.info(f"Created {len(sections)} timestamp-based sections")
        return sections

    def _format_timestamp(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS or MM:SS."""
        total_seconds = int(seconds)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"

    def validate_source(self, source: str | Path) -> None:
        """Validate YouTube URL."""
        super().validate_source(source)

        if isinstance(source, Path):
            raise ValueError("YouTube parser requires a URL, not a file path")

        if not self.can_handle(source):
            raise ValueError(f"Invalid YouTube URL: {source}")
