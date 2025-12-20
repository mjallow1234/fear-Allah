from pydantic_settings import BaseSettings
from typing import List
import os
import re

raw_redis_port = os.getenv("REDIS_PORT", "6379")
match = re.search(r"(\d+)$", raw_redis_port)
PARSED_REDIS_PORT = int(match.group(1)) if match else 6379

class Settings(BaseSettings):
    # Application
    APP_NAME: str = "fear-Allah"
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/fearallah"
    )
    
    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = PARSED_REDIS_PORT
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
    
    # JWT
    JWT_SECRET: str = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    
    # MinIO
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    MINIO_BUCKET: str = os.getenv("MINIO_BUCKET", "fearallah-files")
    MINIO_SECURE: bool = False

    # Upload limits (MB)
    MAX_UPLOAD_MB: int = 50
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1"]
    
    class Config:
        env_file = ".env"

settings = Settings()
