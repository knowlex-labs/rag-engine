from fastapi import FastAPI
from api.routes import collections, config, files, feedback

app = FastAPI(
    title="RAG Engine API",
    description="Core engine for uploading, processing, retrieving, and enriching documents using Retrieval-Augmented Generation (RAG)",
    version="1.0.0"
)

# Include routers
app.include_router(collections.router, prefix="/api/v1", tags=["collections"])
app.include_router(config.router, prefix="/api/v1", tags=["config"])
app.include_router(files.router, prefix="/api/v1", tags=["files"])
app.include_router(feedback.router, prefix="/api/v1", tags=["feedback"])

@app.get("/")
def read_root():
    return {
        "message": "RAG Engine API",
        "version": "1.0.0",
        "docs": "/docs",
        "gradio_ui": "http://localhost:7860"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)