#!/bin/bash

# RAG Engine - Cloud Run Deployment Script
# This script deploys the FastAPI backend to Google Cloud Run

set -e  # Exit on error

# Configuration
PROJECT_ID="nyayamind-dev"
REGION="asia-south1"
SERVICE_NAME="rag-engine-api"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"
GCS_BUCKET_NAME="nyayamind-content-storage"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   RAG Engine - Cloud Run Deployment${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ Error: gcloud CLI is not installed${NC}"
    echo "Install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Set project
echo -e "${YELLOW}🔧 Setting GCP project to: ${PROJECT_ID}${NC}"
gcloud config set project ${PROJECT_ID}

# Enable required APIs
echo -e "${YELLOW}🔧 Enabling required GCP APIs...${NC}"
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    storage.googleapis.com \
    secretmanager.googleapis.com \
    --quiet

# Create GCS bucket if it doesn't exist
echo -e "${YELLOW}🪣 Creating GCS bucket: ${GCS_BUCKET_NAME}${NC}"
if gsutil ls -b gs://${GCS_BUCKET_NAME} 2>/dev/null; then
    echo -e "${GREEN}✅ Bucket already exists${NC}"
else
    gsutil mb -p ${PROJECT_ID} -l ${REGION} gs://${GCS_BUCKET_NAME}
    echo -e "${GREEN}✅ Bucket created${NC}"
fi

# Build Docker image with BuildKit enabled (required for --mount=type=cache)
echo -e "${YELLOW}🐳 Building Docker image with BuildKit...${NC}"
gcloud builds submit --config cloudbuild.yaml --substitutions=_IMAGE_NAME=${IMAGE_NAME} .

# Deploy to Cloud Run
echo -e "${YELLOW}🚀 Deploying to Cloud Run...${NC}"
gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME} \
    --platform managed \
    --region ${REGION} \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 1 \
    --timeout 300 \
    --set-env-vars="GCS_BUCKET_NAME=${GCS_BUCKET_NAME},EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2,VECTOR_SIZE=384" \
    --set-secrets="QDRANT_HOST=QDRANT_HOST:latest,QDRANT_API_KEY=QDRANT_API_KEY:latest,GEMINI_API_KEY=GEMINI_API_KEY:latest,OPENAI_API_KEY=OPENAI_API_KEY:latest,CRITIC_MODEL_API_KEY=CRITIC_MODEL_API_KEY:latest" \
    --max-instances 10 \
    --min-instances 0

# Get service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format 'value(status.url)')

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   ✅ Deployment Successful!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Service URL:${NC} ${SERVICE_URL}"
echo -e "${BLUE}API Docs:${NC} ${SERVICE_URL}/docs"
echo -e "${BLUE}Health Check:${NC} ${SERVICE_URL}/"
echo ""
echo -e "${YELLOW}📝 Next Steps:${NC}"
echo "1. Test the API: curl ${SERVICE_URL}/"
echo "2. View logs: gcloud run services logs read ${SERVICE_NAME} --region ${REGION}"
echo "3. Update Gradio UI with new API URL in api_client.py"
echo ""
