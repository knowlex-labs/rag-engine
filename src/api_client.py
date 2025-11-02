import requests
import logging
import time
from typing import Dict, Any, Optional, List
from io import BytesIO

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RAGAPIClient:
    def __init__(self, base_url: str = "http://localhost:8000/api/v1"):
        self.base_url = base_url

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()

        try:
            logger.info(f"API Call: {method} {url}")
            response = requests.request(method, url, **kwargs)

            elapsed_time = round((time.time() - start_time) * 1000, 2)
            logger.info(f"Response: {response.status_code} in {elapsed_time}ms")

            if response.status_code in [200, 207]:
                return {"success": True, "data": response.json(), "status_code": response.status_code}
            else:
                error_msg = f"API Error: {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f" - {error_detail}"
                except:
                    error_msg += f" - {response.text}"

                logger.error(error_msg)
                return {"success": False, "error": error_msg, "status_code": response.status_code}

        except requests.exceptions.ConnectionError:
            error_msg = "Connection Error: Could not connect to backend API"
            logger.error(error_msg)
            return {"success": False, "error": error_msg, "status_code": 0}
        except Exception as e:
            error_msg = f"Request Error: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg, "status_code": 0}

    # File Management APIs
    def upload_file(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        files = {"file": (filename, BytesIO(file_content), "application/octet-stream")}
        return self._make_request("POST", "/files", files=files)

    def list_files(self) -> Dict[str, Any]:
        return self._make_request("GET", "/files")

    def get_file(self, file_id: str) -> Dict[str, Any]:
        return self._make_request("GET", f"/files/{file_id}")

    def delete_file(self, file_id: str) -> Dict[str, Any]:
        return self._make_request("DELETE", f"/files/{file_id}")

    # Collection Management APIs
    def list_collections(self) -> Dict[str, Any]:
        """List all collections"""
        return self._make_request("GET", "/collections")

    def get_collection(self, collection_name: str) -> Dict[str, Any]:
        """Check if a specific collection exists"""
        return self._make_request("GET", f"/collection/{collection_name}")

    def create_collection(self, name: str, rag_config: Optional[Dict] = None, indexing_config: Optional[Dict] = None) -> Dict[str, Any]:
        data = {"name": name}
        if rag_config:
            data["rag_config"] = rag_config
        if indexing_config:
            data["indexing_config"] = indexing_config

        return self._make_request("POST", "/collection", json=data)

    def delete_collection(self, collection_name: str) -> Dict[str, Any]:
        return self._make_request("DELETE", f"/collection/{collection_name}")


    def link_content(self, collection_name: str, files: List[Dict[str, str]]) -> Dict[str, Any]:
        return self._make_request("POST", f"/{collection_name}/link-content", json=files)

    def unlink_content(self, collection_name: str, file_ids: List[str]) -> Dict[str, Any]:
        return self._make_request("POST", f"/{collection_name}/unlink-content", json=file_ids)

    def query_collection(self, collection_name: str, query: str = "", enable_critic: bool = True) -> Dict[str, Any]:
        data = {"query": query, "enable_critic": enable_critic}
        return self._make_request("POST", f"/{collection_name}/query", json=data)

    def submit_feedback(self, query: str, doc_ids: List[str], label: int, collection: str) -> Dict[str, Any]:
        data = {
            "query": query,
            "doc_ids": doc_ids,
            "label": label,
            "collection": collection
        }
        return self._make_request("POST", "/feedback", json=data)


api_client = RAGAPIClient()