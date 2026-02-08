from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import collections
from config import Config
from utils.logger import setup_logging
from middleware.logging_middleware import LoggingMiddleware

# Setup structured logging
setup_logging(log_level=Config.app.LOG_LEVEL)

app = FastAPI(
    title="RAG Engine API",
    description="Core engine for uploading, processing, retrieving, and enriching documents using Retrieval-Augmented Generation (RAG)",
    version="1.0.0"
)

# Add logging middleware (must be first to capture all requests)
app.add_middleware(LoggingMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.app.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(collections.router, tags=["Collections"])

@app.get("/")
def read_root():
    return {
        "message": "RAG Engine API",
        "version": "1.0.0",
        "docs": "/docs",
        "gradio_ui": "http://localhost:7860"
    }

@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": "2025-11-11T10:36:39Z"}

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
