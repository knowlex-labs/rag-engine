from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import collections, config, files, feedback, users

app = FastAPI(
    title="RAG Engine API",
    description="Core engine for uploading, processing, retrieving, and enriching documents using Retrieval-Augmented Generation (RAG)",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React dev server
        "http://localhost:7860",  # Gradio UI
        "http://localhost:5173",
        "https://parkho-ai-frontend-846780462763.us-central1.run.app",
        "https://ai-content-tutor-846780462763.us-central1.run.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(collections.router, prefix="/api/v1", tags=["collections"])
app.include_router(config.router, prefix="/api/v1", tags=["config"])
app.include_router(files.router, prefix="/api/v1", tags=["files"])
app.include_router(feedback.router, prefix="/api/v1", tags=["feedback"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])

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
    uvicorn.run(app, host="0.0.0.0", port=8000)