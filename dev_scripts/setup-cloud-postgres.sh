#!/bin/bash

# Setup Cloud SQL PostgreSQL for RAG Engine
# Run this BEFORE deploying with deploy-with-postgres.sh

set -e

# Configuration
PROJECT_ID="parkhoai-864b2"
REGION="us-central1"
INSTANCE_NAME="rag-engine-db"
DATABASE_NAME="rag_engine"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Cloud SQL PostgreSQL Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Set project
gcloud config set project ${PROJECT_ID}

# Enable SQL Admin API
echo -e "${YELLOW}🔧 Enabling Cloud SQL Admin API...${NC}"
gcloud services enable sqladmin.googleapis.com --quiet
echo -e "${GREEN}✅ API enabled${NC}"
echo ""

# Check if instance already exists
if gcloud sql instances describe ${INSTANCE_NAME} &>/dev/null; then
    echo -e "${YELLOW}⚠️  Instance ${INSTANCE_NAME} already exists${NC}"
    INSTANCE_EXISTS=true
else
    INSTANCE_EXISTS=false
fi

if [ "$INSTANCE_EXISTS" = false ]; then
    # Prompt for password
    echo -e "${YELLOW}Please enter a secure password for the PostgreSQL database:${NC}"
    read -s POSTGRES_PASSWORD
    echo ""
    
    if [ -z "$POSTGRES_PASSWORD" ]; then
        echo -e "${RED}❌ Password cannot be empty${NC}"
        exit 1
    fi
    
    # Create Cloud SQL instance
    echo -e "${YELLOW}🏗️  Creating Cloud SQL PostgreSQL instance (this may take 5-10 minutes)...${NC}"
    gcloud sql instances create ${INSTANCE_NAME} \
        --project=${PROJECT_ID} \
        --database-version=POSTGRES_15 \
        --tier=db-f1-micro \
        --region=${REGION} \
        --storage-type=SSD \
        --storage-size=10GB \
        --backup \
        --backup-start-time=03:00 \
        --database-flags=max_connections=100
    
    echo -e "${GREEN}✅ Instance created${NC}"
    echo ""
    
    # Set password
    echo -e "${YELLOW}🔐 Setting postgres user password...${NC}"
    gcloud sql users set-password postgres \
        --instance=${INSTANCE_NAME} \
        --password="${POSTGRES_PASSWORD}"
    echo -e "${GREEN}✅ Password set${NC}"
    echo ""
    
    # Create database
    echo -e "${YELLOW}📊 Creating database: ${DATABASE_NAME}${NC}"
    gcloud sql databases create ${DATABASE_NAME} \
        --instance=${INSTANCE_NAME}
    echo -e "${GREEN}✅ Database created${NC}"
    echo ""
else
    echo -e "${YELLOW}Using existing instance. Please enter the postgres password:${NC}"
    read -s POSTGRES_PASSWORD
    echo ""
fi

# Get connection name
CONNECTION_NAME=$(gcloud sql instances describe ${INSTANCE_NAME} \
    --format='value(connectionName)')

echo -e "${GREEN}✅ Cloud SQL PostgreSQL instance ready!${NC}"
echo ""
echo -e "${BLUE}Connection Details:${NC}"
echo "  Instance: ${INSTANCE_NAME}"
echo "  Connection Name: ${CONNECTION_NAME}"
echo "  Database: ${DATABASE_NAME}"
echo "  User: postgres"
echo ""

# Create secrets in Secret Manager
echo -e "${YELLOW}🔐 Creating secrets in Secret Manager...${NC}"

create_or_update_secret() {
    local secret_name=$1
    local secret_value=$2
    
    if gcloud secrets describe ${secret_name} --project=${PROJECT_ID} &>/dev/null; then
        echo -e "${BLUE}Updating secret: ${secret_name}${NC}"
        echo -n "${secret_value}" | gcloud secrets versions add ${secret_name} --data-file=-
    else
        echo -e "${BLUE}Creating secret: ${secret_name}${NC}"
        echo -n "${secret_value}" | gcloud secrets create ${secret_name} --data-file=- --replication-policy="automatic"
    fi
    echo -e "${GREEN}✅ ${secret_name} configured${NC}"
}

# Create PostgreSQL secrets
create_or_update_secret "POSTGRES_HOST" "/cloudsql/${CONNECTION_NAME}"
create_or_update_secret "POSTGRES_PORT" "5432"
create_or_update_secret "POSTGRES_DB" "${DATABASE_NAME}"
create_or_update_secret "POSTGRES_USER" "postgres"
create_or_update_secret "POSTGRES_PASSWORD" "${POSTGRES_PASSWORD}"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   ✅ Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}📝 Next Steps:${NC}"
echo "1. Make sure other secrets are set up: ./setup_secrets.sh"
echo "2. Deploy with PostgreSQL: ./deploy-with-postgres.sh"
echo ""
echo -e "${BLUE}💡 Note: The database schema will be automatically created when the app starts${NC}"
echo ""

