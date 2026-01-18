#!/bin/bash
# Run the Bare Acts Ingestion Tools

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."

# Activate conda environment if available
if command -v conda &> /dev/null; then
    source $(conda info --base)/etc/profile.d/conda.sh
    conda activate rag-engine 2>/dev/null || true
fi

# Run Streamlit
cd "$SCRIPT_DIR"
streamlit run app.py --server.port 8501 --browser.gatherUsageStats false
