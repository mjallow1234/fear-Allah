from minio import Minio
from minio.error import S3Error
import io
from app.core.config import settings


class MinioStorage:
    def __init__(self):
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        self.bucket = settings.MINIO_BUCKET
        self._ensure_bucket()
    
    def _ensure_bucket(self):
        """Create bucket if it doesn't exist"""
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
        except S3Error as e:
            print(f"MinIO bucket error: {e}")
    
    async def upload_file(
        self,
        file_data: bytes,
        filename: str,
        content_type: str = "application/octet-stream"
    ) -> str:
        """Upload file and return path"""
        try:
            file_path = f"uploads/{filename}"
            self.client.put_object(
                self.bucket,
                file_path,
                io.BytesIO(file_data),
                len(file_data),
                content_type=content_type,
            )
            return file_path
        except S3Error as e:
            raise Exception(f"Failed to upload file: {e}")
    
    async def download_file(self, file_path: str) -> bytes:
        """Download file and return content"""
        try:
            response = self.client.get_object(self.bucket, file_path)
            return response.read()
        except S3Error as e:
            raise Exception(f"Failed to download file: {e}")
        finally:
            response.close()
            response.release_conn()
    
    async def delete_file(self, file_path: str):
        """Delete file"""
        try:
            self.client.remove_object(self.bucket, file_path)
        except S3Error as e:
            raise Exception(f"Failed to delete file: {e}")
    
    def get_presigned_url(self, file_path: str, expiry_hours: int = 1) -> str:
        """Get presigned URL for file download"""
        from datetime import timedelta
        try:
            return self.client.presigned_get_object(
                self.bucket,
                file_path,
                expires=timedelta(hours=expiry_hours),
            )
        except S3Error as e:
            raise Exception(f"Failed to generate presigned URL: {e}")


_minio_storage_singleton = None

def get_minio_storage():
    global _minio_storage_singleton
    if _minio_storage_singleton is None:
        try:
            _minio_storage_singleton = MinioStorage()
        except Exception:
            _minio_storage_singleton = None
    return _minio_storage_singleton
