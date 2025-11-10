#!/bin/bash

# RAG Engine Test Runner
# Run different test suites with clear output

set -e

echo "🧪 RAG Engine Test Suite"
echo "========================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}Error: pytest not installed${NC}"
    echo "Install with: pip install -r requirements-test.txt"
    exit 1
fi

# Parse command line arguments
TEST_SUITE=${1:-all}

case $TEST_SUITE in
    all)
        echo -e "${YELLOW}Running ALL tests...${NC}"
        pytest tests/ -v --tb=short
        ;;

    e2e)
        echo -e "${YELLOW}Running E2E tests (user-facing features)...${NC}"
        pytest tests/e2e/ -v --tb=short
        ;;

    unit)
        echo -e "${YELLOW}Running Unit tests (component logic)...${NC}"
        pytest tests/unit/ -v --tb=short
        ;;

    integration)
        echo -e "${YELLOW}Running Integration tests (pipeline flow)...${NC}"
        pytest tests/integration/ -v --tb=short
        ;;

    concept)
        echo -e "${YELLOW}Running Concept Explanation tests...${NC}"
        pytest tests/e2e/test_concept_explanation.py -v --tb=short
        ;;

    questions)
        echo -e "${YELLOW}Running Knowledge Testing tests...${NC}"
        pytest tests/e2e/test_knowledge_testing.py -v --tb=short
        ;;

    problems)
        echo -e "${YELLOW}Running Problem Generation tests...${NC}"
        pytest tests/e2e/test_problem_generation.py -v --tb=short
        ;;

    analogies)
        echo -e "${YELLOW}Running Analogy Generation tests...${NC}"
        pytest tests/e2e/test_analogies.py -v --tb=short
        ;;

    chunking)
        echo -e "${YELLOW}Running Chunking Logic tests...${NC}"
        pytest tests/unit/test_chunking.py -v --tb=short
        ;;

    pipeline)
        echo -e "${YELLOW}Running Query Pipeline tests...${NC}"
        pytest tests/integration/test_query_pipeline.py -v --tb=short
        ;;

    performance)
        echo -e "${YELLOW}Running Performance Benchmark tests...${NC}"
        pytest tests/integration/test_query_pipeline.py::TestPerformanceBenchmarks -v --tb=short
        ;;

    coverage)
        echo -e "${YELLOW}Running tests with coverage report...${NC}"
        pytest tests/ --cov=src --cov-report=html --cov-report=term -v
        echo -e "${GREEN}Coverage report generated: htmlcov/index.html${NC}"
        ;;

    quick)
        echo -e "${YELLOW}Running quick smoke tests...${NC}"
        pytest tests/e2e/test_concept_explanation.py::TestConceptExplanation::test_basic_concept_query -v
        ;;

    help)
        echo "Usage: ./run_tests.sh [TEST_SUITE]"
        echo ""
        echo "Test Suites:"
        echo "  all           - Run all tests (default)"
        echo "  e2e           - End-to-end tests"
        echo "  unit          - Unit tests"
        echo "  integration   - Integration tests"
        echo "  concept       - Concept explanation tests"
        echo "  questions     - Knowledge testing tests"
        echo "  problems      - Problem generation tests"
        echo "  analogies     - Analogy generation tests"
        echo "  chunking      - Chunking logic tests"
        echo "  pipeline      - Query pipeline tests"
        echo "  performance   - Performance benchmarks"
        echo "  coverage      - Run with coverage report"
        echo "  quick         - Quick smoke test"
        echo "  help          - Show this help"
        echo ""
        echo "Examples:"
        echo "  ./run_tests.sh e2e"
        echo "  ./run_tests.sh concept"
        echo "  ./run_tests.sh performance"
        exit 0
        ;;

    *)
        echo -e "${RED}Unknown test suite: $TEST_SUITE${NC}"
        echo "Run './run_tests.sh help' for usage"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}✓ Test run complete${NC}"
