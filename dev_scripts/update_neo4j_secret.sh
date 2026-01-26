#!/bin/bash

# Update Neo4j Password Secret in Google Cloud Secret Manager
# This script reads the NEO4J_PASSWORD from .env and updates the secret

set -e

PROJECT_ID="nyayamind-dev"
SECRET_NAME="NEO4J_PASSWORD"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}🔐 Updating Neo4j Password Secret${NC}"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${RED}❌ Error: .env file not found${NC}"
    exit 1
fi

# Extract NEO4J_PASSWORD from .env
NEO4J_PASSWORD=$(grep "^NEO4J_PASSWORD=" .env | cut -d '=' -f2- | tr -d '"' | tr -d "'")

if [ -z "$NEO4J_PASSWORD" ]; then
    echo -e "${RED}❌ Error: NEO4J_PASSWORD not found in .env${NC}"
    exit 1
fi

echo -e "${YELLOW}📝 Found password in .env (length: ${#NEO4J_PASSWORD} characters)${NC}"
echo ""

# Update the secret
echo -e "${YELLOW}🔄 Updating secret in Google Cloud Secret Manager...${NC}"
echo -n "$NEO4J_PASSWORD" | gcloud secrets versions add $SECRET_NAME \
    --project=$PROJECT_ID \
    --data-file=-

echo ""
echo -e "${GREEN}✅ Secret updated successfully!${NC}"
echo ""
echo -e "${YELLOW}📝 Next steps:${NC}"
echo "1. Redeploy your Cloud Run service to pick up the new secret"
echo "2. Run: ./deploy.sh"
echo ""
