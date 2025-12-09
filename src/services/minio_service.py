from minio import Minio
import logging
from typing import Optional, BinaryIO, Iterator, Tuple
import io
from config import Config

logger = logging.getLogger(__name__)


class MinioService:
    def __init__(self):
        self.host = Config.minio.HOST
        self.access_key = Config.minio.ACCESS_KEY
        self.secret_key = Config.minio.SECRET_KEY
        self.secure = Config.minio.SECURE

        self.client = Minio(
            endpoint=self.host,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure
        )

        logger.info(f"MinIO client initialized: {self.host}")

    def bucket_exists(self, bucket_name: str) -> bool:
        return self.client.bucket_exists(bucket_name)

    def create_bucket(self, bucket_name: str):
        if not self.bucket_exists(bucket_name):
            self.client.make_bucket(bucket_name)
            logger.info(f"Created bucket: {bucket_name}")

    def upload_file(self, bucket_name: str, object_name: str, file_data: BinaryIO, file_size: int) -> bool:
        try:
            self.create_bucket(bucket_name)
            self.client.put_object(
                bucket_name=bucket_name,
                object_name=object_name,
                data=file_data,
                length=file_size
            )
            logger.info(f"Uploaded {object_name} to {bucket_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to upload {object_name}: {e}")
            return False

    def download_file(self, bucket_name: str, object_name: str) -> Optional[bytes]:
        try:
            response = self.client.get_object(bucket_name, object_name)
            return response.read()
        except Exception as e:
            logger.error(f"Failed to download {object_name}: {e}")
            return None

    def delete_file(self, bucket_name: str, object_name: str) -> bool:
        try:
            self.client.remove_object(bucket_name, object_name)
            logger.info(f"Deleted {object_name} from {bucket_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete {object_name}: {e}")
            return False

    def get_file_url(self, bucket_name: str, object_name: str) -> str:
        return f"minio://{bucket_name}/{object_name}"

    def list_objects(self, bucket_name: str, prefix: str = ""):
        try:
            return self.client.list_objects(bucket_name, prefix=prefix)
        except Exception as e:
            logger.error(f"Failed to list objects in {bucket_name}: {e}")
            return []

    def stream_file(self, bucket_name: str, object_name: str) -> Iterator[bytes]:
        """Stream file content in chunks for efficient handling of large files."""
        try:
            with self.client.get_object(bucket_name, object_name) as response:
                chunk_size = 8192  # 8KB chunks
                while chunk := response.read(chunk_size):
                    yield chunk
        except Exception as e:
            logger.error(f"Failed to stream {object_name}: {e}")
            return iter([])

    def get_object_info(self, bucket_name: str, object_name: str) -> Optional[Tuple[int, str]]:
        """Get file size and content type from MinIO object metadata."""
        try:
            stat = self.client.stat_object(bucket_name, object_name)
            # MinIO stat returns size and content_type if available
            return stat.size, stat.content_type or 'application/octet-stream'
        except Exception as e:
            logger.error(f"Failed to get object info for {object_name}: {e}")
            return None


minio_service = MinioService()