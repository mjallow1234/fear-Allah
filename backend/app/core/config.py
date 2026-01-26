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

    # Environment + feature flags
    APP_ENV: str = os.getenv("APP_ENV", "development")  # development | staging | production
    API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:18002")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

    # Feature flags (safe defaults)
    WS_ENABLED: bool = False
    AUTOMATIONS_ENABLED: bool = False

    # Control whether legacy backfill runs automatically at startup.
    # Defaults to False to avoid accidental assignment changes on startup.
    BACKFILL_ON_STARTUP: bool = False

    # Testing flag (set True during pytest runs)
    TESTING: bool = False

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "info")

    # Make.com Webhook Integration (Phase 6.5)
    # If unset, webhook integration is disabled
    MAKE_WEBHOOK_URL: str = os.getenv("MAKE_WEBHOOK_URL", "")

    # Integration API token for external platforms (e.g., Make, Google Sheets)
    # Format: fear_allah_integration_<32chars>
    # If unset, integration access is disabled
    INTEGRATION_API_TOKEN: str | None = None
    
    class Config:
        env_file = ".env"

settings = Settings()

# Configure structured logging once per-process using environment-aware defaults
import logging

level_name = (settings.LOG_LEVEL or '').upper() or (
    'DEBUG' if settings.APP_ENV == 'development' else ('INFO' if settings.APP_ENV == 'staging' else 'WARNING')
)
numeric_level = getattr(logging, level_name, logging.INFO)

# Use a format WITHOUT %(env)s for global basicConfig to avoid breaking third-party loggers
logging.basicConfig(
    level=numeric_level,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)

# Create our app logger with a custom formatter that includes env
logger = logging.getLogger('fear-allah')
logger.handlers.clear()
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter(f'%(asctime)s %(levelname)s %(name)s [{settings.APP_ENV}] %(message)s'))
logger.addHandler(_handler)
logger.propagate = False  # Don't double-log through root

# Safety enforcement: do not allow accidental automations in non-production
if settings.APP_ENV != 'production':
    # Force-disable automations in non-production to be extra safe
    settings.AUTOMATIONS_ENABLED = False

# Production must explicitly opt-in for dangerous capabilities
if settings.APP_ENV == 'production':
    assert settings.WS_ENABLED is True, "WS must be enabled explicitly in production"
    assert settings.AUTOMATIONS_ENABLED is True, "Automations must be enabled explicitly in production"
