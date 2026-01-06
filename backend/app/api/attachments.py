"""
Phase 9.1 - File Attachments API

Endpoints for uploading and managing file attachments in chat.
"""
import os
import logging
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.db.database import get_db
from app.db.models import FileAttachment, Message, Channel, ChannelMember, User
from app.core.security import get_current_user
from app.permissions.constants import Permission
from app.permissions.dependencies import require_permission
from app.storage.local import (
    save_upload_file,
    delete_file,
    get_file_url,
    get_full_path,
    file_exists,
    UPLOAD_DIR,
    MAX_FILE_SIZE,
    ALLOWED_MIME_TYPES,
)
from app.services.audit import log_audit

router = APIRouter()
logger = logging.getLogger(__name__)


# === Response Models ===

class AttachmentResponse(BaseModel):
    id: int
    message_id: Optional[int]
    channel_id: int
    uploader_id: int
    uploader_username: Optional[str] = None
    filename: str
    original_filename: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    url: str
    created_at: datetime

    class Config:
        from_attributes = True


class UploadResponse(BaseModel):
    attachment: AttachmentResponse
    message: str = "File uploaded successfully"


class AttachmentListResponse(BaseModel):
    attachments: List[AttachmentResponse]
    total: int


# === Helper Functions ===

async def check_channel_access(
    db: AsyncSession,
    user_id: int,
    channel_id: int,
    allow_admin: bool = False,
) -> Channel:
    """
    Verify user has access to the channel.

    allow_admin - if True, system admins or users with role 'admin' bypass membership checks
    """
    # Get channel
    result = await db.execute(
        select(Channel).where(Channel.id == channel_id)
    )
    channel = result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    if channel.is_archived:
        raise HTTPException(status_code=403, detail="Cannot upload to archived channel")

    # Admin bypass if allowed
    if allow_admin:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user and (user.is_system_admin or getattr(user, 'role', None) == 'admin'):
            return channel
    
    # Check membership for non-public channels
    if channel.type != "public":
        result = await db.execute(
            select(ChannelMember).where(
                ChannelMember.channel_id == channel_id,
                ChannelMember.user_id == user_id
            )
        )
        membership = result.scalar_one_or_none()
        
        if not membership:
            raise HTTPException(status_code=403, detail="Not a member of this channel")
    
    return channel


def attachment_to_response(attachment: FileAttachment, username: Optional[str] = None) -> AttachmentResponse:
    """Convert FileAttachment model to response."""
    # Use storage_path if available, else fallback to file_path
    path = attachment.storage_path or attachment.file_path
    return AttachmentResponse(
        id=attachment.id,
        message_id=attachment.message_id,
        channel_id=attachment.channel_id,
        uploader_id=attachment.user_id,
        uploader_username=username,
        filename=attachment.filename,
        original_filename=attachment.filename,  # Use filename as original
        file_size=attachment.file_size,
        mime_type=attachment.mime_type,
        url=get_file_url(path),
        created_at=attachment.created_at,
    )


# === Endpoints ===

@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    channel_id: int = Form(...),
    message_id: Optional[int] = Form(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a file attachment.
    
    - File can be standalone (uploaded before message) or attached to existing message
    - Validates file type, size, and user's channel access
    - Emits realtime event if attached to message
    """
    user_id = current_user["user_id"]
    
    # Check channel access
    channel = await check_channel_access(db, user_id, channel_id)
    
    # Track if this is a file-only upload (no existing message)
    is_file_only_message = message_id is None
    created_message = None
    
    # Verify message if provided
    if message_id:
        result = await db.execute(
            select(Message).where(Message.id == message_id)
        )
        message = result.scalar_one_or_none()
        
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        
        if message.is_deleted:
            raise HTTPException(status_code=400, detail="Cannot attach file to a deleted message")

        if message.channel_id != channel_id:
            raise HTTPException(status_code=400, detail="Message is not in specified channel")
    else:
        # No message_id provided - create a file-only message
        # This ensures attachments always have a message to attach to
        created_message = Message(
            content="",  # Empty content for file-only message
            channel_id=channel_id,
            author_id=user_id,
        )
        db.add(created_message)
        await db.flush()  # Flush to get message.id before creating attachment
        message_id = created_message.id
        logger.info(f"Created file-only message {message_id} for channel {channel_id}")
    
    # Get user info for response
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    username = user.username if user else None
    
    try:
        # Save file to storage
        sanitized_name, storage_path, file_size, mime_type = await save_upload_file(
            file=file,
            channel_id=channel_id,
        )
        
        # Create database record
        attachment = FileAttachment(
            message_id=message_id,
            channel_id=channel_id,
            user_id=user_id,
            filename=sanitized_name,
            file_path=storage_path,  # Legacy field
            storage_path=storage_path,
            file_size=file_size,
            mime_type=mime_type,
        )
        
        db.add(attachment)
        await db.commit()
        await db.refresh(attachment)
        
        # Log audit event
        await log_audit(
            db=db,
            action="message.file_uploaded",
            target_type="attachment",
            target_id=attachment.id,
            description=f"Uploaded file '{file.filename}' ({file_size} bytes) to channel {channel_id}",
            meta={
                "filename": file.filename,
                "sanitized_filename": sanitized_name,
                "file_size": file_size,
                "mime_type": mime_type,
                "channel_id": channel_id,
                "message_id": message_id,
            },
            user_id=user_id,
            username=username,
        )
        
        # Emit realtime events
        if message_id:
            try:
                from app.realtime.socket import emit_attachment_added, emit_message_new
                
                attachment_data = {
                    "id": attachment.id,
                    "message_id": message_id,
                    "channel_id": channel_id,
                    "uploader_id": user_id,
                    "uploader_username": username,
                    "filename": sanitized_name,
                    "original_filename": file.filename,
                    "file_size": file_size,
                    "mime_type": mime_type,
                    "url": get_file_url(storage_path),
                    "created_at": attachment.created_at.isoformat(),
                }
                
                # For file-only messages, emit message:new FIRST so frontend has the message
                # before receiving the attachment
                if is_file_only_message and created_message:
                    message_payload = {
                        "id": created_message.id,
                        "content": "",
                        "channel_id": channel_id,
                        "author_id": user_id,
                        "author_username": username,
                        "parent_id": None,
                        "created_at": created_message.created_at.isoformat(),
                        "is_edited": False,
                        "reactions": [],
                        "attachments": [attachment_data],  # Include attachment in message
                    }
                    logger.info(f"Emitting message:new for file-only message {created_message.id}")
                    await emit_message_new(channel_id, message_payload)
                else:
                    # For existing messages, emit attachment_added
                    await emit_attachment_added(channel_id, attachment_data)
                
            except Exception as e:
                # Don't fail upload if realtime emission fails
                logger.warning(f"Failed to emit attachment event: {e}")
        
        logger.info(f"File uploaded: {storage_path} by user {user_id}")
        
        return UploadResponse(
            attachment=attachment_to_response(attachment, username),
            message="File uploaded successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File upload failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload file")


@router.get("/download/{attachment_id}")
async def download_file(
    attachment_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Download a file attachment.
    
    Verifies user has access to the channel containing the attachment.
    """
    user_id = current_user["user_id"]
    
    # Get attachment
    result = await db.execute(
        select(FileAttachment).where(FileAttachment.id == attachment_id)
    )
    attachment = result.scalar_one_or_none()
    
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    # Prefer verifying access based on the message's channel (falls back to attachment.channel_id)
    channel_id_to_check = None
    if attachment.message_id:
        result = await db.execute(select(Message).where(Message.id == attachment.message_id))
        message = result.scalar_one_or_none()
        if message:
            channel_id_to_check = message.channel_id
    if channel_id_to_check is None:
        channel_id_to_check = attachment.channel_id

    # Allow system admins to download attachments even if not a member
    await check_channel_access(db, user_id, channel_id_to_check, allow_admin=True)
    
    # Get file path - use storage_path if available, else file_path
    path = attachment.storage_path or attachment.file_path
    file_path = get_full_path(path)
    
    if not file_path.exists():
        logger.error(f"File not found on disk: {path}")
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    return FileResponse(
        path=file_path,
        filename=attachment.filename,  # Use filename (original is same)
        media_type=attachment.mime_type,
    )


@router.get("/message/{message_id}", response_model=AttachmentListResponse)
async def get_message_attachments(
    message_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all attachments for a message.
    """
    user_id = current_user["user_id"]
    
    # Get message to verify access
    result = await db.execute(
        select(Message).where(Message.id == message_id)
    )
    message = result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    # Check channel access
    await check_channel_access(db, user_id, message.channel_id)
    
    # Get attachments
    result = await db.execute(
        select(FileAttachment, User.username)
        .outerjoin(User, FileAttachment.user_id == User.id)
        .where(FileAttachment.message_id == message_id)
        .order_by(FileAttachment.created_at)
    )
    rows = result.all()
    
    attachments = [
        attachment_to_response(att, username)
        for att, username in rows
    ]
    
    return AttachmentListResponse(
        attachments=attachments,
        total=len(attachments)
    )


@router.get("/channel/{channel_id}", response_model=AttachmentListResponse)
async def get_channel_attachments(
    channel_id: int,
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all attachments in a channel (for file browser).
    """
    user_id = current_user["user_id"]
    
    # Check channel access
    await check_channel_access(db, user_id, channel_id)
    
    # Get attachments with pagination
    result = await db.execute(
        select(FileAttachment, User.username)
        .outerjoin(User, FileAttachment.user_id == User.id)
        .where(FileAttachment.channel_id == channel_id)
        .order_by(FileAttachment.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = result.all()
    
    # Get total count
    from sqlalchemy import func
    count_result = await db.execute(
        select(func.count(FileAttachment.id))
        .where(FileAttachment.channel_id == channel_id)
    )
    total = count_result.scalar() or 0
    
    attachments = [
        attachment_to_response(att, username)
        for att, username in rows
    ]
    
    return AttachmentListResponse(
        attachments=attachments,
        total=total
    )


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attachment(
    attachment_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a file attachment.
    
    Only the uploader or admins can delete attachments.
    """
    user_id = current_user["user_id"]
    
    # Get attachment
    result = await db.execute(
        select(FileAttachment).where(FileAttachment.id == attachment_id)
    )
    attachment = result.scalar_one_or_none()
    
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    # Check permission (uploader or admin)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    is_admin = user and (user.is_system_admin or user.role == "admin")
    is_owner = attachment.user_id == user_id
    
    if not (is_owner or is_admin):
        raise HTTPException(status_code=403, detail="Not authorized to delete this attachment")
    
    # Delete from storage - use storage_path if available, else file_path
    storage_path = attachment.storage_path or attachment.file_path
    try:
        await delete_file(storage_path)
    except Exception as e:
        logger.warning(f"Failed to delete file from disk: {e}")
    
    # Delete from database
    await db.delete(attachment)
    await db.commit()
    
    # Log audit
    await log_audit(
        db=db,
        action="message.file_deleted",
        target_type="attachment",
        target_id=attachment_id,
        description=f"Deleted file '{attachment.filename}'",
        meta={
            "filename": attachment.filename,
            "file_size": attachment.file_size,
            "channel_id": attachment.channel_id,
        },
        user_id=user_id,
        username=user.username if user else None,
    )
    
    logger.info(f"Attachment deleted: {attachment_id} by user {user_id}")
    
    return None


# === Info Endpoints ===

@router.get("/limits")
async def get_upload_limits(
    current_user: dict = Depends(get_current_user),
):
    """
    Get file upload limits and allowed types.
    """
    return {
        "max_file_size_mb": MAX_FILE_SIZE // (1024 * 1024),
        "max_file_size_bytes": MAX_FILE_SIZE,
        "allowed_mime_types": list(ALLOWED_MIME_TYPES),
    }


@router.get("/file/{channel_id}/{date}/{filename}")
async def serve_file(
    channel_id: int,
    date: str,
    filename: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Serve a file by its storage path.
    
    URL format: /api/attachments/file/{channel_id}/{date}/{filename}
    """
    user_id = current_user["user_id"]
    
    # Check channel access
    await check_channel_access(db, user_id, channel_id)
    
    # Build storage path
    storage_path = f"channel_{channel_id}/{date}/{filename}"
    file_path = get_full_path(storage_path)
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    # Look up attachment in DB for mime type
    result = await db.execute(
        select(FileAttachment).where(
            FileAttachment.channel_id == channel_id,
            FileAttachment.filename == filename
        )
    )
    attachment = result.scalar_one_or_none()
    
    mime_type = attachment.mime_type if attachment else "application/octet-stream"
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=mime_type,
    )
