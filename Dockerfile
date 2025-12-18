# Use Python 3.12 slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies (only what's needed for build)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies with cache mount (faster rebuilds, no duplicate cache in image)
# Remove build tools immediately after to save 349MB (only needed during pip install)
# Note: cache mount disappears after RUN, so no need to clean /root/.cache/pip
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt && \
    apt-get purge -y build-essential && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

# Set HuggingFace cache to persist in the image
ENV HF_HOME=/app/hf_cache
ENV TRANSFORMERS_CACHE=/app/hf_cache

# Pre-download embedding model to persist in the image
RUN mkdir -p /app/hf_cache && \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# Copy source code
COPY src/ ./src/

# Create directories and files in one layer
RUN mkdir -p uploads && \
    touch .env

# Expose port (Cloud Run uses 8080)
EXPOSE 8080

# Set environment variables
ENV PYTHONPATH=/app/src

# Run FastAPI - Cloud Run sets PORT env var to 8080
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
