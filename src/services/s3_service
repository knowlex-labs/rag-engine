import logging
import boto3

logger = logging.getLogger(__name__)

class S3Service:
    def __init__(self):
        self.s3_client = boto3.client('s3',
            aws_access_key_id=Config.s3.ACCESS_KEY,
            aws_secret_access_key=Config.s3.SECRET_KEY,
            region_name=Config.s3.REGION_NAME
        )

    def upload_file(self, file_path: str, bucket_name: str, key: str) -> bool:
        try:
            self.s3_client.upload_file(file_path, bucket_name, key)
            return True
        except Exception as e:
            logger.error(f"Failed to upload file to S3: {e}")
            return False

    def download_file(self, bucket_name: str, key: str) -> bytes:
        try:
            return self.s3_client.download_file(bucket_name, key)
        except Exception as e:
            logger.error(f"Failed to download file from S3: {e}")
            return None

