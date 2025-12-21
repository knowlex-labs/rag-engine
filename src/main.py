from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import rag, config, feedback, question_generation, law_query, law_summary, legal_assistant, diagnostics
from config import Config

app = FastAPI(
    title="RAG Engine API",
    description="Core engine for uploading, processing, retrieving, and enriching documents using Retrieval-Augmented Generation (RAG)",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.app.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(rag.router, prefix="/api/v1", tags=["rag"])
app.include_router(config.router, prefix="/api/v1", tags=["config"])
app.include_router(feedback.router, prefix="/api/v1", tags=["feedback"])
app.include_router(question_generation.router)  # Law question generation routes

# Include Law API routes
app.include_router(legal_assistant.router, tags=["Legal Assistant"])
app.include_router(law_query.router, tags=["Legal Query"])
app.include_router(law_summary.router, tags=["Legal Summaries"])
app.include_router(diagnostics.router, tags=["Diagnostics"])
# app.include_router(users.router, prefix="/api/v1/users", tags=["users"]) # REMOVED

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
