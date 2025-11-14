import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class CacheManager:
    def __init__(self, cache_dir: str = ".cache"):
        self.chunks_dir = Path(cache_dir) / "chunks"
        self.collection_files_cache = Path(cache_dir) / "collection_files.json"
        self.chunks_dir.mkdir(parents=True, exist_ok=True)

    def load_chunks(self, file_id: str) -> Optional[List[Dict[str, Any]]]:
        try:
            cache_path = self.chunks_dir / f"{file_id}.json"
            if cache_path.exists():
                with open(cache_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load chunks cache for {file_id}: {e}")
        return None

    def save_chunks(self, file_id: str, documents: List[Dict[str, Any]]) -> bool:
        try:
            cache_path = self.chunks_dir / f"{file_id}.json"
            with open(cache_path, 'w') as f:
                json.dump(documents, f)
            return True
        except Exception as e:
            logger.warning(f"Failed to save chunks cache for {file_id}: {e}")
        return False

    def clear_chunks(self, file_id: str) -> bool:
        try:
            cache_path = self.chunks_dir / f"{file_id}.json"
            if cache_path.exists():
                cache_path.unlink()
                return True
        except Exception as e:
            logger.warning(f"Failed to clear chunks cache for {file_id}: {e}")
        return False

    def has_chunks(self, file_id: str) -> bool:
        return (self.chunks_dir / f"{file_id}.json").exists()

    def load_collection_files_mapping(self) -> Dict[str, List[str]]:
        try:
            if self.collection_files_cache.exists():
                with open(self.collection_files_cache, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load collection-files mapping: {e}")
        return {}

    def save_collection_files_mapping(self, mapping: Dict[str, List[str]]) -> bool:
        try:
            with open(self.collection_files_cache, 'w') as f:
                json.dump(mapping, f)
            return True
        except Exception as e:
            logger.warning(f"Failed to save collection-files mapping: {e}")
        return False

    def add_file_to_collection(self, user_id: str, collection_name: str, file_id: str) -> bool:
        collection_key = f"{user_id}_{collection_name}"
        mapping = self.load_collection_files_mapping()

        if collection_key not in mapping:
            mapping[collection_key] = []

        if file_id not in mapping[collection_key]:
            mapping[collection_key].append(file_id)
            return self.save_collection_files_mapping(mapping)
        return True

    def remove_file_from_collection(self, user_id: str, collection_name: str, file_id: str) -> bool:
        collection_key = f"{user_id}_{collection_name}"
        mapping = self.load_collection_files_mapping()

        if collection_key in mapping and file_id in mapping[collection_key]:
            mapping[collection_key].remove(file_id)
            return self.save_collection_files_mapping(mapping)
        return True

    def get_collection_files(self, user_id: str, collection_name: str) -> List[str]:
        collection_key = f"{user_id}_{collection_name}"
        mapping = self.load_collection_files_mapping()
        return mapping.get(collection_key, [])

    def clear_collection(self, user_id: str, collection_name: str) -> bool:
        collection_key = f"{user_id}_{collection_name}"
        mapping = self.load_collection_files_mapping()
        if collection_key in mapping:
            del mapping[collection_key]
            return self.save_collection_files_mapping(mapping)
        return True