#!/bin/bash

# RAG Engine Docker Setup Script
# Simple setup for all services

set -e

echo "🐳 RAG Engine Docker Setup"
echo "=========================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker compose &> /dev/null; then
    print_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

print_success "Docker and Docker Compose are installed"

# Check if .env file exists
if [ ! -f .env ]; then
    print_warning ".env file not found"
    
    if [ -f env.example ]; then
        print_info "Copying env.example to .env"
        cp env.example .env
        print_warning "Please edit .env file with your API keys"
        echo ""
        echo "Required configuration:"
        echo "  - GEMINI_API_KEY or OPENAI_API_KEY"
        echo "  - POSTGRES_PASSWORD (recommended to change from default)"
        echo ""
        read -p "Press Enter after updating .env file..."
    else
        print_error "env.example not found. Please create .env file manually"
        exit 1
    fi
fi

print_success ".env file found"

echo ""
print_info "Starting all services (PostgreSQL, MinIO, Qdrant, RAG Engine)..."
echo ""

docker compose up -d

echo ""
print_info "Waiting for services to be healthy..."
sleep 10

# Check service status
echo ""
print_info "Service status:"
docker compose ps

echo ""
print_success "🎉 All services started successfully!"
echo ""
echo "📚 Access your services:"
echo "  - RAG Engine API:     http://localhost:8000"
echo "  - API Documentation:  http://localhost:8000/docs"
echo "  - Qdrant Dashboard:   http://localhost:6333/dashboard"
echo "  - MinIO Console:      http://localhost:9001"
echo "  - PostgreSQL:         localhost:5432"
echo ""
echo "📖 Useful commands:"
echo "  View logs:            docker compose logs -f"
echo "  Stop services:        docker compose down"
echo "  Restart a service:    docker compose restart <service-name>"
echo "  Check status:         docker compose ps"
echo ""
echo "Service names: postgres, minio, qdrant, rag-engine"
echo ""
print_success "Setup complete!"
