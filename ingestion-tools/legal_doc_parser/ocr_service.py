"""
OCR Service for Legal Documents
Uses Tesseract to extract text from scanned PDFs.
"""

import os
import logging
from pathlib import Path
from typing import List, Optional
import subprocess

# Set up logging
logger = logging.getLogger(__name__)

class OCRService:
    @staticmethod
    def is_tesseract_available() -> bool:
        """Check if Tesseract is installed on the system."""
        try:
            result = subprocess.run(['tesseract', '--version'], capture_output=True, text=True)
            return result.returncode == 0
        except FileNotFoundError:
            return False

    @staticmethod
    def pdf_to_text(pdf_path: str) -> Optional[str]:
        """Convert a scanned PDF to text using Tesseract."""
        if not OCRService.is_tesseract_available():
            logger.error("Tesseract is not installed. Cannot perform OCR.")
            return None

        try:
            import tempfile
            
            # Use 'pdftoppm' to images then 'tesseract'
            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir_path = Path(tmpdir)
                
                # Convert PDF to images
                logger.info(f"Converting PDF to images for OCR: {pdf_path}")
                # pdftoppm -png <pdf_path> <prefix>
                subprocess.run(['pdftoppm', pdf_path, str(tmpdir_path / 'page'), '-png'], check=True)
                
                # OCR each image
                full_text = []
                image_files = sorted(tmpdir_path.glob('page-*.png'))
                
                if not image_files:
                    logger.warning("No images generated from PDF. Maybe empty or corrupted?")
                    return None

                for img_file in image_files:
                    logger.info(f"OCRing page: {img_file.name}")
                    result = subprocess.run(['tesseract', str(img_file), 'stdout'], capture_output=True, text=True)
                    if result.returncode == 0:
                        full_text.append(result.stdout)
                
                return "\n\n".join(full_text)

        except Exception as e:
            logger.error(f"OCR failed: {e}")
            return None

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        text = OCRService.pdf_to_text(sys.argv[1])
        if text:
            print(text[:1000])
        else:
            print("OCR failed")
