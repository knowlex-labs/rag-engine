from minio import Minio
import os
import logging
from typing import Optional, BinaryIO
import io

logger = logging.getLogger(__name__)


class MinioService:
    def __init__(self):
        self.host = os.getenv("MINIO_HOST", "localhost:9000")
        self.access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        self.secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")
        self.secure = os.getenv("MINIO_SECURE", "false").lower() == "true"

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


minio_service = MinioService()