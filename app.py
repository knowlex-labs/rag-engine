#!/usr/bin/env python3

import sys
import threading
import time
import logging
from pathlib import Path

# Setup paths
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Import config after setting up paths
from config import Config

# Configure logging with environment variable
log_level = getattr(logging, Config.app.LOG_LEVEL, logging.INFO)
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Set up logger
logger = logging.getLogger(__name__)
logger.info(f"🔧 Logging configured at {Config.app.LOG_LEVEL} level")

def run_fastapi():
    """Run FastAPI server"""
    import uvicorn
    from main import app

    logger.info("🚀 Starting FastAPI on port 8000...")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level=Config.app.LOG_LEVEL.lower()
    )

def run_gradio():
    """Run Gradio UI"""
    logger.info("⏳ Waiting for FastAPI to start...")
    time.sleep(3)  # Give FastAPI time to start

    logger.info("🎉 Starting Gradio on port 7860...")
    from gradio_ui import RAGGradioUI
    ui = RAGGradioUI()
    demo = ui.create_interface()

    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        quiet=False,
        inbrowser=False
    )

def main():
    logger.info("🚀 Starting RAG Engine...")

    # Start FastAPI in background thread
    fastapi_thread = threading.Thread(target=run_fastapi, daemon=True)
    fastapi_thread.start()

    # Run Gradio in main thread
    try:
        run_gradio()
    except KeyboardInterrupt:
        logger.info("👋 Shutting down...")
        sys.exit(0)

if __name__ == "__main__":
    main()