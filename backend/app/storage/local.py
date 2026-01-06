"""
Phase 9.1 - Local File Storage Service

Handles file uploads to local disk storage with:
- Configurable upload directory
- Secure filename sanitization
- MIME type validation
- Size limit enforcement
"""
import os
import re
import uuid
import hashlib
try:
    import aiofiles
except Exception:
    aiofiles = None

from pathlib import Path
from datetime import datetime
from typing import BinaryIO, Optional, Tuple
from fastapi import UploadFile, HTTPException

from app.core.config import settings


# Configuration from environment or defaults
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads/chat")
MAX_FILE_SIZE = settings.MAX_UPLOAD_MB * 1024 * 1024  # Convert MB to bytes

# MIME type whitelist - only these types are allowed
ALLOWED_MIME_TYPES = {
    # Images
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/svg+xml",
    # Documents
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",  # .pptx
    # Text
    "text/plain",
    "text/csv",
    "text/markdown",
    "application/json",
    # Archives
    "application/zip",
    "application/x-zip-compressed",
    "application/x-rar-compressed",
    "application/x-7z-compressed",
}

# Blocked extensions (executables, scripts)
BLOCKED_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".com", ".msi", ".scr",
    ".ps1", ".vbs", ".js", ".jse", ".wsf", ".wsh",
    ".sh", ".bash", ".csh", ".ksh",
    ".py", ".pyw", ".rb", ".pl", ".php",
    ".dll", ".sys", ".drv",
    ".app", ".dmg", ".pkg",  # macOS
    ".deb", ".rpm",  # Linux
}


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal and other attacks.
    
    - Removes path separators
    - Removes null bytes
    - Limits length
    - Replaces dangerous characters
    """
    if not filename:
        return "unnamed_file"
    
    # Remove path components (prevent directory traversal)
    filename = os.path.basename(filename)
    
    # Remove null bytes
    filename = filename.replace("\x00", "")
    
    # Remove or replace dangerous characters
    # Keep alphanumeric, dots, hyphens, underscores
    filename = re.sub(r'[^\w\-.]', '_', filename)
    
    # Prevent double extensions that could hide real type
    # e.g., "file.txt.exe" -> "file_txt.exe"
    parts = filename.rsplit('.', 1)
    if len(parts) == 2:
        name, ext = parts
        name = name.replace('.', '_')
        filename = f"{name}.{ext}"
    
    # Limit filename length (255 is typical filesystem limit)
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:200 - len(ext)] + ext
    
    return filename or "unnamed_file"


def generate_storage_filename(original_filename: str, channel_id: int) -> Tuple[str, str]:
    """
    Generate a unique storage filename to prevent collisions.
    
    Returns:
        Tuple of (storage_filename, relative_storage_path)
    """
    # Get sanitized filename
    safe_name = sanitize_filename(original_filename)
    name, ext = os.path.splitext(safe_name)
    
    # Create unique filename with UUID
    unique_id = uuid.uuid4().hex[:12]
    timestamp = datetime.utcnow().strftime("%Y%m%d")
    
    # Format: channelX/YYYYMMDD/originalname_uuid.ext
    storage_filename = f"{name}_{unique_id}{ext}"
    relative_path = f"channel_{channel_id}/{timestamp}/{storage_filename}"
    
    return storage_filename, relative_path


def validate_file_type(filename: str, content_type: Optional[str]) -> str:
    """
    Validate file type against whitelist.
    
    Returns validated MIME type or raises HTTPException.
    """
    # Check blocked extensions first
    ext = os.path.splitext(filename.lower())[1]
    if ext in BLOCKED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' is not allowed for security reasons"
        )
    
    # Validate MIME type
    if content_type and content_type in ALLOWED_MIME_TYPES:
        return content_type
    
    # Try to infer from extension if MIME not provided
    import mimetypes
    guessed_type, _ = mimetypes.guess_type(filename)
    
    if guessed_type and guessed_type in ALLOWED_MIME_TYPES:
        return guessed_type
    
    # Default fallback for unknown but safe types
    if ext in {".txt", ".log", ".md"}:
        return "text/plain"
    
    raise HTTPException(
        status_code=400,
        detail=f"File type '{content_type or ext}' is not allowed. Allowed types: images, PDFs, documents, text files."
    )


def validate_file_size(size: int) -> None:
    """
    Validate file size against limit.
    """
    if size > MAX_FILE_SIZE:
        max_mb = settings.MAX_UPLOAD_MB
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {max_mb}MB"
        )
    
    if size == 0:
        raise HTTPException(
            status_code=400,
            detail="Empty files are not allowed"
        )


async def save_upload_file(
    file: UploadFile,
    channel_id: int,
) -> Tuple[str, str, int, str]:
    if aiofiles is None:
        raise HTTPException(status_code=500, detail="Server missing aiofiles dependency for file uploads")
    """
    Save an uploaded file to local storage.
    
    Args:
        file: FastAPI UploadFile object
        channel_id: Channel ID for organizing files
    
    Returns:
        Tuple of (sanitized_filename, storage_path, file_size, mime_type)
    
    Raises:
        HTTPException on validation failure
    """
    # Validate MIME type
    mime_type = validate_file_type(file.filename or "unnamed", file.content_type)
    
    # Generate storage path
    sanitized_name, relative_path = generate_storage_filename(
        file.filename or "unnamed",
        channel_id
    )
    
    # Create full path
    full_path = Path(UPLOAD_DIR) / relative_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Read file content to get size and save
    content = await file.read()
    file_size = len(content)
    
    # Validate size
    validate_file_size(file_size)
    
    # Save file
    async with aiofiles.open(full_path, 'wb') as f:
        await f.write(content)
    
    return sanitized_name, relative_path, file_size, mime_type


async def delete_file(storage_path: str) -> bool:
    """
    Delete a file from storage.
    
    Returns True if deleted, False if file didn't exist.
    """
    full_path = Path(UPLOAD_DIR) / storage_path
    
    if full_path.exists():
        full_path.unlink()
        return True
    
    return False


def get_file_url(storage_path: str) -> str:
    """
    Get the URL path for accessing a file.
    
    storage_path format: channel_X/YYYYMMDD/filename.ext
    URL format: /api/attachments/file/X/YYYYMMDD/filename.ext
    """
    # Parse storage path and convert to URL
    parts = storage_path.split('/')
    if len(parts) >= 3 and parts[0].startswith('channel_'):
        channel_id = parts[0].replace('channel_', '')
        date = parts[1]
        filename = '/'.join(parts[2:])  # Handle any nested paths
        return f"/api/attachments/file/{channel_id}/{date}/{filename}"
    
    # Fallback for old format
    return f"/api/attachments/file/{storage_path}"


def get_full_path(storage_path: str) -> Path:
    """
    Get the full filesystem path for a storage path.
    """
    return Path(UPLOAD_DIR) / storage_path


def file_exists(storage_path: str) -> bool:
    """
    Check if a file exists in storage.
    """
    return get_full_path(storage_path).exists()
