# Use Python 3.12 slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies (without gradio for production)
RUN pip install --no-cache-dir -r requirements.txt

# Set HuggingFace cache to persist in the image
ENV HF_HOME=/app/hf_cache
ENV TRANSFORMERS_CACHE=/app/hf_cache

# Pre-download embedding model to persist in the image
RUN mkdir -p /app/hf_cache && \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# Copy source code
COPY src/ ./src/

# Create uploads directory
RUN mkdir -p uploads

# Create empty .env file (secrets will be injected via Cloud Run env vars)
RUN touch .env

# Expose port (Cloud Run uses 8080)
EXPOSE 8080

# Set environment variables
ENV PYTHONPATH=/app/src

# Run FastAPI - Cloud Run sets PORT env var to 8080
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
