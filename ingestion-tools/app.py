"""
Bare Acts Ingestion Tools - Main Application
Internal tool for parsing, indexing, and testing bare acts documents.

Features:
- PDF parsing with OCR fallback
- JSON review and editing
- GCS upload and Neo4j indexing
- Real-time status tracking
- Document filtering for queries
- Uses backend API at localhost:8000
"""

import streamlit as st
import sys
import json
import requests
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# Add parent directory to path for imports
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "src"))

# API Configuration
API_BASE_URL = "http://localhost:8000"
API_TIMEOUT = 45

# Page config
st.set_page_config(
    page_title="Bare Acts Ingestion Tools",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1E3A5F;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #6B7280;
        margin-bottom: 2rem;
    }
    .log-container {
        background: #1E1E1E;
        color: #00FF00;
        font-family: 'Courier New', monospace;
        padding: 1rem;
        border-radius: 8px;
        max-height: 300px;
        overflow-y: auto;
    }
    .settings-button {
        position: fixed;
        top: 1rem;
        right: 1rem;
        z-index: 999;
    }
    .indexed-doc {
        background: #E8F5E9;
        border-left: 4px solid #4CAF50;
        padding: 0.75rem;
        margin: 0.5rem 0;
        border-radius: 4px;
    }
    .new-doc {
        background: #FFF3E0;
        border-left: 4px solid #FF9800;
        padding: 0.75rem;
        margin: 0.5rem 0;
        border-radius: 4px;
    }
    .chat-message {
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 8px;
    }
    .user-message {
        background: #E3F2FD;
        margin-left: 2rem;
    }
    .assistant-message {
        background: #F5F5F5;
        margin-right: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'logs' not in st.session_state:
    st.session_state.logs = []
if 'parsed_files' not in st.session_state:
    st.session_state.parsed_files = []
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'indexed_documents' not in st.session_state:
    st.session_state.indexed_documents = []
if 'selected_docs_for_query' not in st.session_state:
    st.session_state.selected_docs_for_query = []
if 'select_all_mode' not in st.session_state:
    st.session_state.select_all_mode = False
if 'settings' not in st.session_state:
    st.session_state.settings = {
        'api_base_url': API_BASE_URL,
        'gcs_bucket': 'nyayamind-content-storage',
        'neo4j_uri': 'bolt://localhost:7687',
        'embedding_provider': 'gemini',
        'enable_ocr': False,
        'ocr_provider': 'tesseract'
    }


# === Helper Functions ===

def add_log(message: str, level: str = "INFO"):
    """Add a log message to session state."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.logs.append(f"[{timestamp}] {level}: {message}")
    if len(st.session_state.logs) > 100:
        st.session_state.logs = st.session_state.logs[-100:]


def fetch_indexed_documents() -> List[Dict]:
    """Fetch list of indexed documents from Neo4j."""
    try:
        from src.services.graph_service import get_graph_service
        graph = get_graph_service()
        if graph:
            result = graph.execute_query("""
                MATCH (s:Statute)
                RETURN s.id as id, s.name as name, s.year as year, 
                       s.total_sections as sections, s.indexed_at as indexed_at,
                       s.document_type as doc_type
                ORDER BY s.indexed_at DESC
            """)
            if result:
                return [dict(r) for r in result]
    except Exception as e:
        add_log(f"Failed to fetch indexed documents: {e}", "WARNING")
    return []


def check_api_status() -> bool:
    """Check if backend API is reachable."""
    try:
        url = f"{st.session_state.settings.get('api_base_url', API_BASE_URL)}/health"
        response = requests.get(url, timeout=5)
        return response.status_code == 200
    except:
        return False


def show_logs_section():
    """Show logs section (used on all pages)."""
    with st.expander("📜 Activity Logs", expanded=False):
        if st.session_state.logs:
            log_text = "\n".join(st.session_state.logs[-30:])
            st.code(log_text, language="", height=250)
        else:
            st.caption("No activity yet...")


# === Main Application ===

def main():
    # Settings button in top right
    col1, col2, col3 = st.columns([0.7, 0.15, 0.15])
    with col2:
        api_status = check_api_status()
        if api_status:
            st.success("🟢 API Connected")
        else:
            st.error("🔴 API Offline")
    with col3:
        if st.button("⚙️ Settings", use_container_width=True):
            st.session_state.show_settings = not st.session_state.get('show_settings', False)
            st.rerun()
    
    # Settings Modal
    if st.session_state.get('show_settings', False):
        show_settings_modal()
    
    # Main header
    st.markdown('<p class="main-header">⚖️ Bare Acts Ingestion Tools</p>', unsafe_allow_html=True)
    st.markdown("---")
    
    # Three main tabs
    tab1, tab2, tab3 = st.tabs([
        "📤 1. Upload & Parse",
        "📋 2. Review & Ingest",
        "💬 3. Chat with Documents"
    ])
    
    with tab1:
        show_upload_parse_tab()
    
    with tab2:
        show_review_ingest_tab()
    
    with tab3:
        show_chat_tab()


# === TAB 1: Upload & Parse ===

def show_upload_parse_tab():
    """Tab 1: Upload PDFs and parse them."""
    
    st.markdown("### 📄 Upload PDF Documents")
    st.caption("Upload bare act PDFs to extract structured content")
    
    # Check for existing parsed files to detect duplicates
    output_dir = Path(__file__).parent / "output"
    existing_files = list(output_dir.glob("*.json")) if output_dir.exists() else []
    existing_names = set()
    for f in existing_files:
        try:
            with open(f, 'r') as file:
                data = json.load(file)
                name = data.get('name', '').lower().strip()
                if name:
                    existing_names.add(name)
        except:
            pass
    
    uploaded_files = st.file_uploader(
        "Select PDF files",
        type=['pdf'],
        accept_multiple_files=True,
        help="Upload one or more PDF files to parse",
        key="pdf_uploader"
    )
    
    if uploaded_files:
        st.info(f"📁 {len(uploaded_files)} file(s) selected")
        
        # Check for potential duplicates
        duplicates = []
        for uploaded_file in uploaded_files:
            file_name_clean = uploaded_file.name.replace('.pdf', '').replace('_', ' ').lower().strip()
            for existing_name in existing_names:
                if file_name_clean in existing_name or existing_name in file_name_clean:
                    duplicates.append(uploaded_file.name)
                    break
        
        if duplicates:
            st.warning(f"⚠️ {len(duplicates)} potential duplicate(s) - delete existing files first if re-parsing")
        
        col1, col2 = st.columns([0.5, 0.5])
        with col1:
            force_ocr = st.checkbox("🔍 Use OCR (scanned PDFs)", value=False)
        with col2:
            if st.button("⚡ Start Parsing", type="primary", use_container_width=True):
                parse_uploaded_files(uploaded_files, force_ocr)
    
    st.markdown("---")
    
    # Show parsed files in compact list
    json_files = list(output_dir.glob("*.json")) if output_dir.exists() else []
    
    if json_files:
        # Pagination
        if 'page_num' not in st.session_state:
            st.session_state.page_num = 0
        
        files_per_page = 25
        total_pages = (len(json_files) - 1) // files_per_page + 1
        
        st.markdown(f"### 📚 Parsed Files ({len(json_files)})")
        
        # Pagination controls
        col1, col2, col3 = st.columns([0.3, 0.4, 0.3])
        with col1:
            if st.button("⬅️ Previous", disabled=st.session_state.page_num == 0):
                st.session_state.page_num -= 1
                st.rerun()
        with col2:
            st.markdown(f"<center>Page {st.session_state.page_num + 1} of {total_pages}</center>", unsafe_allow_html=True)
        with col3:
            if st.button("Next ➡️", disabled=st.session_state.page_num >= total_pages - 1):
                st.session_state.page_num += 1
                st.rerun()
        
        st.markdown("---")
        
        # Get files for current page
        start_idx = st.session_state.page_num * files_per_page
        end_idx = min(start_idx + files_per_page, len(json_files))
        page_files = json_files[start_idx:end_idx]
        
        # Compact list display
        for i, f in enumerate(page_files, start=start_idx + 1):
            try:
                with open(f, 'r') as file:
                    data = json.load(file)
                
                act_name = data.get('name', 'Unknown Act')
                year = data.get('year', 0)
                sections = data.get('total_sections', 0)
                
                # Compact row
                col1, col2, col3, col4, col5 = st.columns([0.05, 0.5, 0.15, 0.15, 0.15])
                
                with col1:
                    st.caption(f"{i}.")
                
                with col2:
                    if sections == 0:
                        st.markdown(f"⚠️ **{act_name}**")
                    else:
                        st.markdown(f"**{act_name}**")
                
                with col3:
                    if year and year > 0:
                        st.caption(f"📅 {year}")
                    else:
                        st.caption("📅 —")
                
                with col4:
                    if sections == 0:
                        st.caption(f"⚠️ 0 sections")
                    else:
                        st.caption(f"📄 {sections} sections")
                
                with col5:
                    if st.button("🗑️", key=f"del_{f.name}", help=f"Delete {f.name}"):
                        f.unlink()
                        add_log(f"Deleted {f.name}")
                        st.rerun()
                
            except Exception as e:
                col1, col2, col3 = st.columns([0.05, 0.8, 0.15])
                with col1:
                    st.caption(f"{i}.")
                with col2:
                    st.error(f"Error: {f.name}")
                with col3:
                    if st.button("🗑️", key=f"del_err_{f.name}"):
                        f.unlink()
                        st.rerun()
    else:
        st.info("No parsed files yet. Upload PDFs above to get started.")
    
    st.markdown("---")
    show_logs_section()


def parse_uploaded_files(files, use_ocr=False):
    """Parse uploaded PDF files."""
    import tempfile
    
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, file in enumerate(files):
        status_text.text(f"Parsing {file.name}...")
        add_log(f"Parsing: {file.name}")
        
        try:
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                tmp.write(file.read())
                tmp_path = tmp.name
            
            from legal_doc_parser.bare_act_parser import BareActParser
            
            parser = BareActParser(debug=False)
            result = parser.parse_pdf(tmp_path, use_ocr=use_ocr)
            parsed_dict = result.to_dict()
            
            output_name = file.name.replace('.pdf', '.json').replace(' ', '_').lower()
            output_path = output_dir / output_name
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(parsed_dict, f, indent=2, ensure_ascii=False)
            
            add_log(f"✅ Parsed {file.name}: {parsed_dict['total_sections']} sections")
            Path(tmp_path).unlink()
            
        except Exception as e:
            add_log(f"❌ Error parsing {file.name}: {str(e)}", "ERROR")
            st.error(f"Failed: {file.name}")
        
        progress_bar.progress((i + 1) / len(files))
    
    status_text.success("✅ Parsing complete!")
    add_log("Parsing batch complete")
    st.rerun()


# === TAB 2: Review & Ingest ===

def show_review_ingest_tab():
    """Tab 2: Review parsed files and ingest to Neo4j."""
    
    output_dir = Path(__file__).parent / "output"
    json_files = list(output_dir.glob("*.json")) if output_dir.exists() else []
    
    if not json_files:
        st.info("No parsed files available. Go to 'Upload & Parse' tab first.")
        show_logs_section()
        return
    
    st.markdown("### 📋 Review & Select Files for Ingestion")
    
    # Auto-refresh indexed documents on page load
    if 'last_refresh_time' not in st.session_state:
        st.session_state.last_refresh_time = 0
    
    import time
    current_time = time.time()
    if current_time - st.session_state.last_refresh_time > 5:  # Auto-refresh every 5+ seconds
        with st.spinner("Fetching indexed documents..."):
            st.session_state.indexed_documents = fetch_indexed_documents()
            st.session_state.last_refresh_time = current_time
            if st.session_state.indexed_documents:
                add_log(f"Loaded {len(st.session_state.indexed_documents)} indexed documents")
    
    # Manual refresh button
    if st.button("🔄 Refresh Indexed Status", use_container_width=True):
        with st.spinner("Fetching..."):
            st.session_state.indexed_documents = fetch_indexed_documents()
            st.session_state.last_refresh_time = time.time()
            add_log(f"Refreshed: {len(st.session_state.indexed_documents)} indexed documents")
        st.rerun()
    
    indexed_names = set()
    for doc in st.session_state.indexed_documents:
        if doc.get('name'):
            indexed_names.add(doc['name'].lower())
    
    # Quick selection buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✨ Select New Only", use_container_width=True):
            st.session_state.select_all_mode = False
            st.rerun()
    with col2:
        button_label = "❌ Deselect All" if st.session_state.select_all_mode else "✅ Select All"
        if st.button(button_label, use_container_width=True):
            st.session_state.select_all_mode = not st.session_state.select_all_mode
            st.rerun()
    
    st.markdown("---")
    
    # Categorize and sort files (new files first, then indexed)
    new_files = []
    indexed_files = []
    
    for f in json_files:
        try:
            with open(f, 'r') as file:
                data = json.load(file)
                act_name = data.get('name', '').lower()
        except:
            act_name = f.stem.replace('_', ' ').lower()
        
        is_indexed = any(act_name in idx or idx in act_name for idx in indexed_names)
        
        if is_indexed:
            indexed_files.append((f, act_name, True))
        else:
            new_files.append((f, act_name, False))
    
    # Sort: new files first, then indexed files
    sorted_files = new_files + indexed_files
    
    # File selection
    selected_files = []
    
    st.markdown(f"**📊 {len(new_files)} new files, {len(indexed_files)} already indexed**")
    st.markdown("---")
    
    for f, act_name, is_indexed in sorted_files:
        # Check if file has content
        has_content = True
        try:
            with open(f, 'r') as file:
                data = json.load(file)
                total_sections = data.get('total_sections', 0)
                has_content = total_sections > 0
        except:
            has_content = False
        
        # Default selection - don't select empty files
        if st.session_state.select_all_mode:
            default_value = True and has_content
        else:
            default_value = not is_indexed and has_content  # Select only new files with content
        
        col1, col2, col3, col4 = st.columns([0.05, 0.5, 0.2, 0.25])
        with col1:
            selected = st.checkbox("Select", value=default_value, key=f"sel_{f.name}", 
                                   label_visibility="collapsed", disabled=not has_content)
        with col2:
            if not has_content:
                st.markdown(f"⚠️ `{f.name}` (empty)")
            else:
                st.markdown(f"`{f.name}`")
        with col3:
            try:
                with open(f, 'r') as file:
                    data = json.load(file)
                sections = data.get('total_sections', 0)
                if sections == 0:
                    st.caption("⚠️ No sections")
                else:
                    st.caption(f"{sections} sections")
            except:
                st.caption("—")
        with col4:
            if not has_content:
                st.markdown("❌ **Empty**")
            elif is_indexed:
                st.markdown("✅ **Indexed**")
            else:
                st.markdown("🆕 **New**")
        
        if selected:
            selected_files.append(f)
        
        # Expandable details
        with st.expander(f"📄 View {f.name}", expanded=False):
            try:
                with open(f, 'r') as file:
                    data = json.load(file)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Sections", data.get('total_sections', 0))
                with col2:
                    st.metric("Chapters", data.get('total_chapters', 0))
                with col3:
                    st.metric("Year", data.get('year', 'N/A'))
                
                st.markdown(f"**Act Name:** {data.get('name', 'Unknown')}")
                
                # Warning for empty files
                if data.get('total_sections', 0) == 0:
                    st.error("⚠️ **This file has no sections!**")
                    st.warning("This is likely a scanned PDF. Try re-parsing with OCR enabled.")
                    text_length = data.get('metadata', {}).get('text_length', 0)
                    st.caption(f"Only {text_length} characters extracted from PDF")
                    
                    if st.button(f"🔄 Re-parse with OCR", key=f"reparse_ocr_{f.name}"):
                        st.info("Please delete this file and upload the original PDF again with OCR enabled in the 'Upload & Parse' tab.")
                
                if st.toggle("🔍 View JSON", key=f"toggle_{f.name}"):
                    st.json(data)
                
            except Exception as e:
                st.error(f"Error reading file: {e}")
    
    st.caption(f"✓ {len(selected_files)} of {len(json_files)} files selected")
    
    st.markdown("---")
    
    # Ingestion options
    st.markdown("### 🚀 Ingestion Settings")
    
    col1, col2 = st.columns(2)
    with col1:
        upload_gcs = st.checkbox("☁️ Upload to GCS", value=True)
        st.caption(f"Bucket: {st.session_state.settings.get('gcs_bucket', 'nyayamind-content-storage')}")
    with col2:
        target_type = st.selectbox(
            "Target Type",
            ["bare_act", "bns", "constitution"],
            key="target_type_ingest"
        )
    
    if st.button("🚀 Start Ingestion", type="primary", use_container_width=True, 
                 disabled=len(selected_files) == 0):
        run_ingestion(selected_files, upload_gcs, True, True, target_type)
    
    st.markdown("---")
    show_logs_section()


def run_ingestion(json_files: List[Path], upload_gcs: bool, index_neo4j: bool, 
                  generate_embeddings: bool, target_type: str = "bare_act"):
    """Run the ingestion pipeline."""
    add_log(f"🚀 Starting ingestion for {len(json_files)} files...")
    
    status_containers = {}
    for f in json_files:
        st.markdown(f"#### 📄 {f.name}")
        status_containers[f.name] = {
            'gcs': st.empty(),
            'neo4j': st.empty(),
            'total': st.empty()
        }
        status_containers[f.name]['total'].info("⏳ Pending...")

    progress_bar = st.progress(0)
    
    for idx, f in enumerate(json_files):
        f_name = f.name
        add_log(f"Processing {idx+1}/{len(json_files)}: {f_name}")
        status_containers[f_name]['total'].warning("⏳ Processing...")
        
        # GCS Upload
        if upload_gcs:
            status_containers[f_name]['gcs'].markdown("☁️ **GCS:** Uploading...")
            try:
                # Use GCS Python client instead of gsutil
                from google.cloud import storage
                import os
                
                bucket_name = st.session_state.settings.get('gcs_bucket', 'nyayamind-content-storage')
                destination_path = f"bare-acts-parsed/{f.name}"
                
                add_log(f"Uploading to gs://{bucket_name}/{destination_path}")
                
                # Set credentials path if not already set
                credentials_file = Path(__file__).parent.parent / "nyayamind-dev-firebase-adminsdk-fbsvc-db8b836225.json"
                if credentials_file.exists():
                    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(credentials_file)
                    add_log(f"Using credentials: {credentials_file.name}")
                
                # Initialize GCS client
                storage_client = storage.Client()
                bucket = storage_client.bucket(bucket_name)
                blob = bucket.blob(destination_path)
                
                # Upload file
                blob.upload_from_filename(str(f))
                
                status_containers[f_name]['gcs'].markdown("☁️ **GCS:** ✅ Success")
                add_log(f"✅ GCS uploaded: {f_name}")
                
            except Exception as e:
                error_msg = str(e)
                status_containers[f_name]['gcs'].markdown(f"☁️ **GCS:** ❌ Failed")
                add_log(f"❌ GCS failed for {f_name}: {error_msg}", "ERROR")
                st.error(f"GCS Error: {error_msg}")
                
                # Provide helpful hints
                if "could not find default credentials" in error_msg.lower() or "was not found" in error_msg.lower():
                    st.warning("💡 Run `gcloud auth application-default login` to authenticate")
                    st.caption(f"Or ensure service account key exists at: {credentials_file}")
                elif "403" in error_msg or "permission" in error_msg.lower():
                    st.warning(f"💡 Check that you have write permissions to bucket: {bucket_name}")

        # Neo4j Indexing
        if index_neo4j:
            status_containers[f_name]['neo4j'].markdown("🗄️ **Neo4j:** Indexing...")
            try:
                script_map = {
                    "bare_act": "ingest_bare_acts.py",
                    "bns": "ingest_bns.py",
                    "constitution": "ingest_constitution.py"
                }
                script_name = script_map.get(target_type, "ingest_bare_acts.py")
                script_path = Path(__file__).parent / script_name
                
                if not script_path.exists():
                    raise FileNotFoundError(f"Ingestion script not found: {script_path}")
                
                import os
                import subprocess
                
                cmd = [sys.executable, str(script_path), "--json-file", str(f)]
                if target_type == "bare_act":
                    cmd.append("--no-clean")
                
                add_log(f"Running: {' '.join(cmd)}")
                
                result = subprocess.run(
                    cmd,
                    cwd=str(Path(__file__).parent.parent),
                    capture_output=True, text=True,
                    env={**os.environ, 'PYTHONPATH': str(Path(__file__).parent.parent)},
                    timeout=300
                )
                
                if result.returncode == 0:
                    status_containers[f_name]['neo4j'].markdown("🗄️ **Neo4j:** ✅ Indexed")
                    add_log(f"✅ Neo4j indexed: {f_name}")
                    
                    # Parse and log stats
                    for line in result.stdout.split('\n'):
                        if any(x in line.lower() for x in ['processed', 'created', 'indexed', 'acts', 'sections', 'chunks']):
                            add_log(f"  > {line.strip()}")
                else:
                    error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                    status_containers[f_name]['neo4j'].markdown("🗄️ **Neo4j:** ❌ Failed")
                    add_log(f"❌ Neo4j failed for {f_name}", "ERROR")
                    add_log(f"Error output: {error_msg[-500:]}", "ERROR")
                    st.error(f"Neo4j Indexing Error for {f_name}")
                    with st.expander("View Error Details"):
                        st.code(error_msg[-1000:])
                    
            except subprocess.TimeoutExpired:
                msg = f"Neo4j indexing timed out for {f_name} (>5 minutes)"
                status_containers[f_name]['neo4j'].markdown("🗄️ **Neo4j:** ⚠️ Timeout")
                add_log(msg, "WARNING")
                st.warning(msg)
            except FileNotFoundError as e:
                status_containers[f_name]['neo4j'].markdown("🗄️ **Neo4j:** ❌ Script not found")
                add_log(f"❌ {str(e)}", "ERROR")
                st.error(str(e))
            except Exception as e:
                status_containers[f_name]['neo4j'].markdown("🗄️ **Neo4j:** ❌ Error")
                add_log(f"❌ Neo4j error for {f_name}: {str(e)}", "ERROR")
                st.error(f"Neo4j Error: {str(e)}")

        status_containers[f_name]['total'].success("✅ Complete")
        progress_bar.progress((idx + 1) / len(json_files))

    st.success("🎉 Ingestion complete!")
    add_log("Ingestion batch complete")
    
    # Refresh indexed documents
    with st.spinner("Refreshing indexed documents..."):
        st.session_state.indexed_documents = fetch_indexed_documents()
        add_log(f"Refreshed: {len(st.session_state.indexed_documents)} indexed documents")


# === TAB 3: Chat with Documents ===

def show_chat_tab():
    """Tab 3: Full-screen chat interface with document filtering."""
    
    st.markdown("### 💬 Chat with Indexed Documents")
    
    # Refresh indexed docs
    if st.button("🔄 Refresh Document List"):
        with st.spinner("Fetching indexed documents..."):
            st.session_state.indexed_documents = fetch_indexed_documents()
            add_log(f"Fetched {len(st.session_state.indexed_documents)} indexed documents")
        st.rerun()
    
    docs = st.session_state.indexed_documents
    
    if not docs:
        st.warning("No indexed documents found. Index some documents in the 'Review & Ingest' tab first.")
        st.info("Click 'Refresh Document List' to check for newly indexed documents.")
        show_logs_section()
        return
    
    st.markdown("---")
    
    # Document filter section
    st.markdown("### 🔍 Filter Documents")
    
    col1, col2 = st.columns(2)
    
    with col1:
        scope_options = {
            "All Legal Documents": ["bare_acts", "bns", "constitution"],
            "Bare Acts Only": ["bare_acts"],
            "BNS Only": ["bns"],
            "Constitution Only": ["constitution"]
        }
        
        selected_scope = st.selectbox(
            "Query Scope",
            list(scope_options.keys()),
            key="query_scope"
        )
        query_scopes = scope_options.get(selected_scope, ["bare_acts"])
    
    with col2:
        doc_names = [d.get('name', 'Unknown') for d in docs]
        selected_docs = st.multiselect(
            "Specific Documents (optional)",
            doc_names,
            key="selected_docs_filter",
            help="Leave empty to search all documents in scope"
        )
        st.session_state.selected_docs_for_query = selected_docs
    
    # Show selected documents
    if selected_docs:
        st.info(f"🎯 Filtering to {len(selected_docs)} specific document(s)")
    else:
        st.info(f"🌐 Searching across all {len(docs)} indexed documents")
    
    st.markdown("---")
    
    # Chat interface
    st.markdown("### 💭 Conversation")
    
    # Chat history container
    chat_container = st.container(height=500)
    with chat_container:
        if not st.session_state.chat_history:
            st.caption("👋 Ask a question about the indexed legal documents...")
        
        for msg in st.session_state.chat_history:
            if msg['role'] == 'user':
                with st.chat_message("user"):
                    st.write(msg['content'])
            else:
                with st.chat_message("assistant"):
                    st.markdown(msg['content'])
    
    # Chat input
    query = st.chat_input("Ask about the indexed documents...", key="chat_input")
    
    if query:
        st.session_state.chat_history.append({'role': 'user', 'content': query})
        
        with chat_container:
            with st.chat_message("user"):
                st.write(query)
            
            with st.chat_message("assistant"):
                with st.spinner("Searching..."):
                    response = run_query(query, query_scopes)
                    st.markdown(response)
                    st.session_state.chat_history.append({'role': 'assistant', 'content': response})
        
        st.rerun()
    
    # Clear chat button
    col1, col2, col3 = st.columns([0.7, 0.15, 0.15])
    with col2:
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.chat_history = []
            st.rerun()
    
    st.markdown("---")
    show_logs_section()


def run_query(query: str, scopes: List[str]) -> str:
    """Run a query via the RAG Engine API."""
    api_url = f"{st.session_state.settings.get('api_base_url', API_BASE_URL)}/api/v1/law/query"
    
    payload = {
        "question": query,
        "scope": scopes,
        "answer_style": "student_friendly",
        "max_sources": 5
    }
    
    selected_docs = st.session_state.get('selected_docs_for_query', [])
    if selected_docs:
        payload["document_filter"] = selected_docs
    
    headers = {
        "Content-Type": "application/json",
        "X-User-Id": "ingestion-tool-admin"
    }
    
    try:
        add_log(f"Query: {query[:50]}... | Scope: {scopes}")
        response = requests.post(api_url, json=payload, headers=headers, timeout=API_TIMEOUT)
        
        if response.status_code == 200:
            data = response.json()
            answer = data.get("answer", "No answer provided.")
            sources = data.get("sources", [])
            
            output = f"**Answer:**\n\n{answer}\n\n"
            
            if sources:
                output += "---\n\n**📚 Sources:**\n\n"
                for i, src in enumerate(sources[:5], 1):
                    title = src.get("title", "Unknown Source")
                    excerpt = src.get("text_excerpt", "")[:200]
                    art_num = src.get("article_number", src.get("section_number", ""))
                    label = f"{art_num}: {title}" if art_num else title
                    output += f"{i}. **{label}**\n\n_{excerpt}..._\n\n"
            
            add_log(f"✅ Query successful - {len(sources)} sources")
            return output
        else:
            add_log(f"❌ Query failed: HTTP {response.status_code}", "ERROR")
            return f"❌ **API Error ({response.status_code})**\n\n{response.text[:300]}"
            
    except requests.exceptions.ConnectionError:
        add_log("❌ Connection error", "ERROR")
        return "❌ **Connection Error**\n\nCannot connect to the API. Make sure the RAG Engine is running on port 8000."
    except requests.exceptions.Timeout:
        add_log("❌ Timeout", "ERROR")
        return "❌ **Timeout**\n\nThe query took too long. Try a simpler question."
    except Exception as e:
        add_log(f"❌ Error: {e}", "ERROR")
        return f"❌ **Error**: {str(e)}"


# === Settings Modal ===

def show_settings_modal():
    """Settings configuration modal."""
    st.markdown("---")
    st.markdown("## ⚙️ Settings")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### API Configuration")
        st.session_state.settings['api_base_url'] = st.text_input(
            "API Base URL",
            value=st.session_state.settings.get('api_base_url', API_BASE_URL)
        )
        
        st.markdown("### Storage")
        st.session_state.settings['gcs_bucket'] = st.text_input(
            "GCS Bucket",
            value=st.session_state.settings.get('gcs_bucket', 'nyayamind-content-storage')
        )
    
    with col2:
        st.markdown("### Database")
        st.session_state.settings['neo4j_uri'] = st.text_input(
            "Neo4j URI",
            value=st.session_state.settings.get('neo4j_uri', 'bolt://localhost:7687')
        )
        
        st.markdown("### Embedding")
        st.session_state.settings['embedding_provider'] = st.selectbox(
            "Provider",
            ["gemini", "openai"],
            index=0 if st.session_state.settings.get('embedding_provider') == 'gemini' else 1
        )
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Save Settings", use_container_width=True, type="primary"):
            add_log("Settings saved")
            st.session_state.show_settings = False
            st.success("✅ Settings saved!")
            st.rerun()
    with col2:
        if st.button("❌ Close", use_container_width=True):
            st.session_state.show_settings = False
            st.rerun()


if __name__ == "__main__":
    main()
