# Bare Acts Ingestion Tools

Internal tool for parsing, indexing, and testing Indian Bare Acts documents.

## Quick Start

```bash
# From the rag-engine directory
cd ingestion-tools

# Install dependencies (if not already in main venv)
pip install -r requirements.txt

# Run the app
streamlit run app.py
```

Or use the run script:
```bash
./run.sh
```

## Workflow

### 1. Parse PDFs
- Upload bare act PDF files
- Tool extracts chapters, sections, and content
- Outputs JSON files to `output/` folder

### 2. Review Results
- Preview parsed JSON files
- Download individual or all files
- Delete or re-parse if needed

### 3. Upload & Index
- Upload JSONs to GCS bucket
- Index in Neo4j with embeddings
- Creates Statute → Chapter → Section hierarchy

### 4. Test Queries
- Always available - works with existing indexed data
- Ask questions to verify indexing
- View source sections

## Settings

Click the ⚙️ Settings button to configure:
- **OpenAI API Key** - For embeddings
- **Gemini API Key** - For chat
- **Embedding Provider** - OpenAI or HuggingFace
- **GCS Bucket** - Cloud storage location
- **OCR Settings** - For scanned PDFs

## File Structure

```
ingestion-tools/
├── app.py              # Main Streamlit application
├── requirements.txt    # Python dependencies
├── run.sh             # Quick start script
├── output/            # Parsed JSON files
└── README.md          # This file
```

## Notes

- Parsed files are stored in `output/` folder
- Logs are displayed in real-time during operations
- Settings are saved in session (configure each session)
