from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
import logging
import traceback
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from collections import defaultdict

from app.db.database import get_db
from app.db.models import Message, Channel, User, MessageReaction, AuditLog, FileAttachment, ChannelMember
from app.core.security import get_current_user, check_user_can_post
from app.permissions.constants import Permission
from app.permissions.dependencies import require_permission

router = APIRouter()

logger = logging.getLogger(__name__)


class MessageCreateRequest(BaseModel):
    content: str
    channel_id: int
    parent_id: Optional[int] = None


class ReactionResponse(BaseModel):
    emoji: str
    count: int
    users: List[int]


class AttachmentResponse(BaseModel):
    id: int
    filename: str
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    url: str
    created_at: datetime

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    id: int
    content: str
    channel_id: int
    author_id: int
    parent_id: Optional[int]
    is_edited: bool
    edited_at: Optional[str] = None
    is_pinned: bool = False
    thread_count: int = 0
    last_activity_at: Optional[str] = None
    created_at: datetime
    author_username: Optional[str] = None
    reactions: List[ReactionResponse] = []
    reply_count: int = 0
    attachments: List[AttachmentResponse] = []

    class Config:
        from_attributes = True


class MessageUpdateRequest(BaseModel):
    content: str


class ReactionRequest(BaseModel):
    emoji: str


def transform_attachment_to_response(attachment: FileAttachment) -> dict:
    """Transform a FileAttachment model to response dict."""
    # Generate the URL based on storage path
    # Format: /api/attachments/file/{channel_id}/{date}/{filename}
    from datetime import datetime
    date_str = attachment.created_at.strftime('%Y-%m-%d') if attachment.created_at else datetime.now().strftime('%Y-%m-%d')
    url = f"/api/attachments/file/{attachment.channel_id}/{date_str}/{attachment.filename}"
    
    return {
        "id": attachment.id,
        "filename": attachment.filename,
        "file_size": attachment.file_size,
        "mime_type": attachment.mime_type,
        "url": url,
        "created_at": attachment.created_at,
    }


def transform_message_to_response(message: Message, author_username: str = None, reply_count: int = 0) -> dict:
    """Transform a Message model to response dict with grouped reactions and attachments."""
    # Group reactions by emoji
    reactions_grouped = defaultdict(lambda: {"count": 0, "users": []})
    for reaction in message.reactions:
        reactions_grouped[reaction.emoji]["count"] += 1
        reactions_grouped[reaction.emoji]["users"].append(reaction.user_id)
    
    reactions_list = [
        {"emoji": emoji, "count": data["count"], "users": data["users"]}
        for emoji, data in reactions_grouped.items()
    ]
    
    # Transform attachments
    attachments_list = []
    if hasattr(message, 'attachments') and message.attachments:
        attachments_list = [transform_attachment_to_response(a) for a in message.attachments]
    
    # Safely access possibly-expired attributes (avoid triggering async lazy loads outside session)
    try:
        edited_at_val = message.edited_at.isoformat() if message.edited_at else None
    except Exception as _:
        logger = logging.getLogger(__name__)
        logger.warning(f"Could not read edited_at for message {getattr(message, 'id', None)}; returning None")
        try:
            edited_at_val = str(message.edited_at) if getattr(message, 'edited_at', None) else None
        except Exception:
            edited_at_val = None

    return {
        "id": message.id,
        "content": message.content,
        "channel_id": message.channel_id,
        "author_id": message.author_id,
        "parent_id": message.parent_id,
        "is_edited": message.is_edited,
        "edited_at": edited_at_val,
        "is_pinned": getattr(message, 'is_pinned', False),
        "thread_count": getattr(message, 'thread_count', 0) or reply_count,
        "last_activity_at": message.last_activity_at.isoformat() if message.last_activity_at else message.created_at.isoformat(),
        "created_at": message.created_at,
        "author_username": author_username or (message.author.username if message.author else None),
        "reactions": reactions_list,
        "reply_count": reply_count,
        "attachments": attachments_list,
    }


@router.post("/", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def create_message(
    request: MessageCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Check if user can post (not banned or muted)
    can_post = await check_user_can_post(db, current_user["user_id"])
    if not can_post:
        raise HTTPException(status_code=403, detail="You are not allowed to post messages (banned or muted)")
    
    # Verify channel exists and not archived
    query = select(Channel).where(Channel.id == request.channel_id)
    result = await db.execute(query)
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    if getattr(channel, 'is_archived', False):
        raise HTTPException(status_code=403, detail="Cannot post to archived channel")
    
    # Get username for broadcasting
    query = select(User).where(User.id == current_user["user_id"])
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    username = user.username if user else "Unknown"

    # Verify parent message if provided and update thread metadata
    parent_msg = None
    if request.parent_id:
        query = select(Message).where(Message.id == request.parent_id)
        result = await db.execute(query)
        parent_msg = result.scalar_one_or_none()
        if not parent_msg:
            raise HTTPException(status_code=404, detail="Parent message not found")

    # Check for slash command handling (do not persist slash command messages)
    try:
        from app.chat.slash_commands import handle_slash_command
        result = await handle_slash_command(raw_text=request.content, user=user, channel=channel, db=db)
        if result.handled:
            # Return a system response (do not save the message)
            # Use JSONResponse to avoid response_model validation since this is a synthetic system message
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=201, content={"system": True, "content": result.response_message or result.error})
    except Exception:
        # If slash handling fails, fall back to normal message creation but log the error
        logger.exception("Slash command handler failed")

    message = Message(
        content=request.content,
        channel_id=request.channel_id,
        author_id=current_user["user_id"],
        parent_id=request.parent_id,
    )
    db.add(message)
    
    # Update parent message thread metadata
    if parent_msg:
        parent_msg.thread_count = (parent_msg.thread_count or 0) + 1
        parent_msg.last_activity_at = func.now()
    
    await db.commit()
    
    # Re-fetch with relationships loaded
    query = (
        select(Message)
        .options(selectinload(Message.reactions), selectinload(Message.author), selectinload(Message.attachments))
        .where(Message.id == message.id)
    )
    result = await db.execute(query)
    message = result.scalar_one()
    
    # Broadcast to WebSocket clients and emit per-user unread updates
    try:
        from app.api.ws import manager, create_mention_notifications
        from app.db.models import ChannelMember
        from app.services.unread import get_unread_count

        await manager.broadcast_to_channel(request.channel_id, {
            "type": "message",
            "id": message.id,
            "content": message.content,
            "user_id": current_user["user_id"],
            "username": username,
            "channel_id": request.channel_id,
            "timestamp": message.created_at.isoformat(),
            "reactions": [],
        })

        # Create notifications for @mentions
        await create_mention_notifications(
            db, request.content, current_user["user_id"], username, request.channel_id, message.id
        )

        # Emit unread_update for each channel member except sender
        members_q = select(ChannelMember).where(ChannelMember.channel_id == request.channel_id)
        members_res = await db.execute(members_q)
        members = members_res.scalars().all()
        for m in members:
            if m.user_id == current_user["user_id"]:
                continue
            unread = await get_unread_count(db, request.channel_id, m.user_id)
            await manager.send_to_user(m.user_id, {
                "type": "unread_update",
                "channel_id": request.channel_id,
                "unread_count": unread,
            })
    except Exception as e:
        # Don't fail the request if broadcast fails
        print(f"Failed to broadcast message or emit unread updates: {e}")
    
    # Socket.IO emit for Phase 4.1 real-time (additive to existing WebSocket)
    try:
        from app.realtime.socket import emit_message_new, emit_thread_reply
        
        message_payload = {
            "id": message.id,
            "content": message.content,
            "channel_id": request.channel_id,
            "author_id": current_user["user_id"],
            "author_username": username,
            "parent_id": request.parent_id,
            "created_at": message.created_at.isoformat(),
            "is_edited": False,
            "reactions": [],
        }
        
        if request.parent_id:
            # Thread reply
            logger.info(f"Emitting thread:reply to channel {request.channel_id} parent {request.parent_id} payload_id {message.id}")
            await emit_thread_reply(request.channel_id, request.parent_id, message_payload)
        else:
            # New message
            logger.info(f"Emitting message:new to channel {request.channel_id} payload_id {message.id}")
            await emit_message_new(request.channel_id, message_payload)
    except Exception as e:
        # Don't fail REST if Socket.IO emit fails
        logger.warning(f"Socket.IO emit failed: {e}")
    
    return transform_message_to_response(message)


@router.get("/channel/{channel_id}", response_model=List[MessageResponse])
async def get_channel_messages(
    channel_id: int,
    skip: int = 0,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify channel access (members only for non-public channels)
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    if getattr(channel, 'is_archived', False):
        raise HTTPException(status_code=403, detail="Cannot view messages for archived channel")
    
    # Get user's membership to determine join date (required for all channels)
    result = await db.execute(select(ChannelMember).where(ChannelMember.channel_id == channel_id, ChannelMember.user_id == current_user['user_id']))
    membership = result.scalar_one_or_none()
    
    # For non-public channels, membership is required
    if channel.type != 'public' and not membership:
        raise HTTPException(status_code=403, detail="Not a member of this channel")
    
    # Privacy guard: Only show messages sent after user joined the channel
    # If no membership record exists (e.g., public channel never explicitly joined), show all messages
    join_timestamp = membership.created_at if membership else None

    # Only get top-level messages (no parent_id) for the main channel view
    query = (
        select(Message)
        .options(selectinload(Message.reactions), selectinload(Message.author), selectinload(Message.attachments))
        .where(
            Message.channel_id == channel_id,
            Message.is_deleted == False,
            Message.parent_id.is_(None)  # Only top-level messages
        )
    )
    
    # Filter by join date if membership exists
    if join_timestamp:
        query = query.where(Message.created_at >= join_timestamp)
    
    query = query.order_by(desc(Message.created_at)).offset(skip).limit(limit)
    result = await db.execute(query)
    messages = result.scalars().all()
    
    # Get reply counts for each message
    message_ids = [m.id for m in messages]
    reply_counts = {}
    if message_ids:
        reply_query = (
            select(Message.parent_id, func.count(Message.id))
            .where(Message.parent_id.in_(message_ids), Message.is_deleted == False)
            .group_by(Message.parent_id)
        )
        reply_result = await db.execute(reply_query)
        reply_counts = dict(reply_result.all())
    
    # Transform and return in chronological order
    return [
        transform_message_to_response(msg, reply_count=reply_counts.get(msg.id, 0))
        for msg in reversed(messages)
    ]


@router.get("/{message_id}/replies", response_model=List[MessageResponse])
async def get_message_replies(
    message_id: int,
    skip: int = 0,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all replies to a specific message (thread view)."""
    # Verify parent message exists
    parent_query = select(Message).where(Message.id == message_id)
    parent_result = await db.execute(parent_query)
    parent_msg = parent_result.scalar_one_or_none()
    
    if not parent_msg or parent_msg.is_deleted:
        raise HTTPException(status_code=404, detail="Message not found")
    
    # Privacy guard: Get user's join timestamp for the channel
    membership_query = select(ChannelMember).where(
        ChannelMember.channel_id == parent_msg.channel_id,
        ChannelMember.user_id == current_user['user_id']
    )
    membership_result = await db.execute(membership_query)
    membership = membership_result.scalar_one_or_none()
    join_timestamp = membership.created_at if membership else None
    
    # Get replies
    query = (
        select(Message)
        .options(selectinload(Message.reactions), selectinload(Message.author), selectinload(Message.attachments))
        .where(Message.parent_id == message_id, Message.is_deleted == False)
    )
    
    # Filter by join date if membership exists
    if join_timestamp:
        query = query.where(Message.created_at >= join_timestamp)
    
    query = query.order_by(Message.created_at).offset(skip).limit(limit)  # Chronological order for threads
    result = await db.execute(query)
    replies = result.scalars().all()
    
    return [transform_message_to_response(msg) for msg in replies]


class ReplyCreateRequest(BaseModel):
    content: str


@router.post("/{message_id}/reply", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def create_reply(
    message_id: int,
    request: ReplyCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a reply to a specific message (thread reply)."""
    # Verify parent message exists
    parent_query = select(Message).where(Message.id == message_id, Message.is_deleted == False)
    parent_result = await db.execute(parent_query)
    parent_msg = parent_result.scalar_one_or_none()
    
    if not parent_msg:
        raise HTTPException(status_code=404, detail="Parent message not found")
    
    # Create the reply
    reply = Message(
        content=request.content,
        channel_id=parent_msg.channel_id,
        author_id=current_user["user_id"],
        parent_id=message_id,
    )
    db.add(reply)
    
    # Update parent message thread metadata
    parent_msg.thread_count = (parent_msg.thread_count or 0) + 1
    parent_msg.last_activity_at = func.now()
    
    await db.commit()
    
    # Re-fetch with relationships loaded
    query = (
        select(Message)
        .options(selectinload(Message.reactions), selectinload(Message.author), selectinload(Message.attachments))
        .where(Message.id == reply.id)
    )
    result = await db.execute(query)
    reply = result.scalar_one()

    # Socket.IO emit for real-time thread reply
    try:
        from app.realtime.socket import emit_thread_reply
        
        username = reply.author.username if reply.author else f"user_{current_user['user_id']}"
        reply_payload = {
            "id": reply.id,
            "content": reply.content,
            "channel_id": reply.channel_id,
            "author_id": current_user["user_id"],
            "author_username": username,
            "parent_id": message_id,
            "created_at": reply.created_at.isoformat(),
            "is_edited": False,
            "reactions": [],
        }
        logger.info(f"Emitting thread:reply for reply {reply.id} to parent {message_id} in channel {reply.channel_id}")
        await emit_thread_reply(reply.channel_id, message_id, reply_payload)
    except Exception as e:
        logger.warning(f"Socket.IO emit failed for thread reply: {e}")
    
    return transform_message_to_response(reply)


@router.get("/{message_id}", response_model=MessageResponse)
async def get_message(
    message_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(Message)
        .options(selectinload(Message.reactions), selectinload(Message.author), selectinload(Message.attachments))
        .where(Message.id == message_id, Message.is_deleted == False)
    )
    result = await db.execute(query)
    message = result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    return transform_message_to_response(message)


@router.patch("/{message_id}", response_model=MessageResponse)
async def update_message(
    message_id: int,
    request: MessageUpdateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        logger.info(f"Update message request received: message_id={message_id}, user_id={current_user.get('user_id')}")

        query = (
            select(Message)
            .options(selectinload(Message.reactions), selectinload(Message.author), selectinload(Message.attachments))
            .where(Message.id == message_id)
        )
        result = await db.execute(query)
        message = result.scalar_one_or_none()

        if not message:
            logger.info(f"Message not found: message_id={message_id}")
            raise HTTPException(status_code=404, detail="Message not found")

        if message.is_deleted:
            raise HTTPException(status_code=400, detail="Cannot edit a deleted message")

        logger.info(f"Message owner: message_id={message_id}, owner_id={message.author_id}")

        # Permission: author or system admin
        user_q = await db.execute(select(User).where(User.id == current_user["user_id"]))
        user = user_q.scalar_one()
        if message.author_id != user.id and not user.is_system_admin:
            raise HTTPException(status_code=403, detail="Permission denied")

        # Validate content (PATCH must update content and must be non-empty)
        if not request.content or not request.content.strip():
            raise HTTPException(status_code=400, detail="Content must be non-empty")

        # Audit info - before/after
        before_content = message.content

        # Apply update
        message.content = request.content
        message.is_edited = True
        message.edited_at = func.now()
        message.editor_id = current_user["user_id"]
        message.last_activity_at = func.now()
        await db.commit()

        # Re-fetch the updated message with relationships to avoid lazy-loaded attribute access
        query = (
            select(Message)
            .options(selectinload(Message.reactions), selectinload(Message.author), selectinload(Message.attachments))
            .where(Message.id == message.id)
        )
        result = await db.execute(query)
        message = result.scalar_one()

        # Audit log
        from app.services.audit import log_audit_from_user
        user_q = await db.execute(select(User).where(User.id == current_user["user_id"]))
        actor = user_q.scalar_one()
        await log_audit_from_user(
            db,
            actor,
            action="message.edited",
            target_type="message",
            target_id=message.id,
            description=f"Message edited in channel {message.channel_id}",
            meta={"before": before_content, "after": message.content, "channel_id": message.channel_id}
        )

        # Emit socket event
        try:
            from app.realtime.socket import emit_message_updated
            payload = transform_message_to_response(message)
            await emit_message_updated(message.channel_id, payload)
        except Exception as e:
            logger.warning(f"Socket emit failed for message updated: {e}")

        logger.info(f"Message updated successfully: message_id={message_id}, editor_id={current_user.get('user_id')}")

        return transform_message_to_response(message)

    except HTTPException:
        # Re-raise known HTTP errors (404, 403, 400) so FastAPI handles them normally
        raise
    except Exception as e:
        # Log full traceback and return 500
        logger.exception(f"Unhandled error updating message_id={message_id}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{message_id}")
async def delete_message(
    message_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):

    query = select(Message).where(Message.id == message_id)
    result = await db.execute(query)
    message = result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    if message.is_deleted:
        raise HTTPException(status_code=400, detail="Message already deleted")

    # Only author or system admin can delete
    user_q = await db.execute(select(User).where(User.id == current_user["user_id"]))
    user = user_q.scalar_one()
    if message.author_id != user.id and not user.is_system_admin:
        raise HTTPException(status_code=403, detail="Permission denied")

    # Soft delete
    message.is_deleted = True
    message.deleted_at = func.now()
    await db.commit()

    # Audit
    from app.services.audit import log_audit_from_user
    user_q = await db.execute(select(User).where(User.id == current_user["user_id"]))
    actor = user_q.scalar_one()
    await log_audit_from_user(
        db,
        actor,
        action="message.deleted",
        target_type="message",
        target_id=message.id,
        description=f"Message soft-deleted in channel {message.channel_id}",
        meta={"message_id": message.id, "channel_id": message.channel_id}
    )

    # Emit socket event
    try:
        from app.realtime.socket import emit_message_deleted
        await emit_message_deleted(message.channel_id, message.id)
    except Exception as e:
        logger.warning(f"Socket emit failed for message deleted: {e}")

    return {"success": True}


# ============================================================
# Pin / unpin endpoints (Phase 9.5.1)
# ============================================================

@router.post("/{message_id}/pin")
async def pin_message(
    message_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify message exists
    query = select(Message).where(Message.id == message_id)
    result = await db.execute(query)
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    if message.is_deleted:
        raise HTTPException(status_code=400, detail="Cannot pin a deleted message")

    # Permission check: message.pin
    from app.permissions.repository import get_system_roles, get_channel_roles
    from app.permissions.service import PermissionService

    system_roles = await get_system_roles(db, current_user["user_id"])
    channel_roles = await get_channel_roles(db, current_user["user_id"], message.channel_id)

    # System admin bypass
    user_q = await db.execute(select(User).where(User.id == current_user["user_id"]))
    user = user_q.scalar_one()
    if user.is_system_admin:
        allowed = True
    else:
        allowed = PermissionService.has_permission(permission=Permission.PIN_MESSAGE, system_roles=system_roles, channel_roles=channel_roles)

    if not allowed:
        raise HTTPException(status_code=403, detail="Permission denied")

    if not message.is_pinned:
        message.is_pinned = True
        await db.commit()

        # Audit
        from app.services.audit import log_audit_from_user
        user_q = await db.execute(select(User).where(User.id == current_user["user_id"]))
        actor = user_q.scalar_one()
        await log_audit_from_user(db, actor, action="message.pinned", target_type="message", target_id=message.id, description=f"Message pinned in channel {message.channel_id}", meta={"message_id": message.id, "channel_id": message.channel_id})

        # Emit
        try:
            from app.realtime.socket import emit_message_pinned
            await emit_message_pinned(message.channel_id, message.id)
        except Exception as e:
            logger.warning(f"Socket emit failed for message pinned: {e}")

    return {"success": True}


@router.delete("/{message_id}/pin")
async def unpin_message(
    message_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Message).where(Message.id == message_id)
    result = await db.execute(query)
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    if message.is_deleted:
        raise HTTPException(status_code=400, detail="Cannot unpin a deleted message")

    # Permission check
    from app.permissions.repository import get_system_roles, get_channel_roles
    from app.permissions.service import PermissionService

    system_roles = await get_system_roles(db, current_user["user_id"])
    channel_roles = await get_channel_roles(db, current_user["user_id"], message.channel_id)

    # System admin bypass
    user_q = await db.execute(select(User).where(User.id == current_user["user_id"]))
    user = user_q.scalar_one()
    if user.is_system_admin:
        allowed = True
    else:
        allowed = PermissionService.has_permission(permission=Permission.PIN_MESSAGE, system_roles=system_roles, channel_roles=channel_roles)

    if not allowed:
        raise HTTPException(status_code=403, detail="Permission denied")

    if message.is_pinned:
        message.is_pinned = False
        await db.commit()

        # Audit
        from app.services.audit import log_audit_from_user
        user_q = await db.execute(select(User).where(User.id == current_user["user_id"]))
        actor = user_q.scalar_one()
        await log_audit_from_user(db, actor, action="message.unpinned", target_type="message", target_id=message.id, description=f"Message unpinned in channel {message.channel_id}", meta={"message_id": message.id, "channel_id": message.channel_id})

        # Emit
        try:
            from app.realtime.socket import emit_message_unpinned
            await emit_message_unpinned(message.channel_id, message.id)
        except Exception as e:
            logger.warning(f"Socket emit failed for message unpinned: {e}")

    return {"success": True}


# ============================================================
# Emoji Reactions (Phase 9.3)
# ============================================================

@router.get("/{message_id}/reactions", response_model=List[ReactionResponse])
async def get_message_reactions(
    message_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all reactions for a message, grouped by emoji.
    
    Response format:
    [
      {"emoji": "👍", "count": 3, "users": [1, 4, 7]},
      {"emoji": "❤️", "count": 2, "users": [2, 5]}
    ]
    """
    # Verify message exists and is not deleted
    msg_query = select(Message).where(Message.id == message_id)
    msg_result = await db.execute(msg_query)
    message = msg_result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    if message.is_deleted:
        raise HTTPException(status_code=404, detail="Message has been deleted")
    
    # Get all reactions for this message
    query = select(MessageReaction).where(MessageReaction.message_id == message_id)
    result = await db.execute(query)
    reactions = result.scalars().all()
    
    # Group by emoji
    reaction_map = {}
    for r in reactions:
        if r.emoji not in reaction_map:
            reaction_map[r.emoji] = {"emoji": r.emoji, "count": 0, "users": []}
        reaction_map[r.emoji]["count"] += 1
        reaction_map[r.emoji]["users"].append(r.user_id)
    
    return list(reaction_map.values())


class ReactionToggleResponse(BaseModel):
    action: str  # "added" or "removed"
    emoji: str
    message_id: int
    reactions: List[ReactionResponse]  # Current state of all reactions


@router.post("/{message_id}/reactions", response_model=ReactionToggleResponse)
async def toggle_reaction(
    message_id: int,
    request: ReactionRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Toggle a reaction on a message (Mattermost-style).
    
    - If reaction exists → remove it
    - If reaction doesn't exist → add it
    
    Validation:
    - Emoji must be 1-32 characters
    - Message must exist and not be deleted
    - User must be a member of the channel
    
    Emits realtime events: message:reaction_added or message:reaction_removed
    """
    import json
    from app.db.models import ChannelMember
    
    user_id = current_user["user_id"]
    emoji = request.emoji.strip()
    
    # Validate emoji
    if not emoji:
        raise HTTPException(status_code=400, detail="Emoji cannot be empty")
    
    # Enforce a maximum payload size for emoji by bytes to prevent abuse from
    # repeated multibyte characters (e.g., many emoji). Use UTF-8 byte length.
    if len(emoji.encode('utf-8')) > 32:
        raise HTTPException(status_code=400, detail="Emoji must be 32 bytes or less when UTF-8 encoded")
    
    # Verify message exists and is not deleted
    msg_query = (
        select(Message)
        .options(selectinload(Message.author))
        .where(Message.id == message_id)
    )
    msg_result = await db.execute(msg_query)
    message = msg_result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    if message.is_deleted:
        raise HTTPException(status_code=403, detail="Cannot react to a deleted message")
    
    # Verify user is a member of the channel
    membership_query = select(ChannelMember).where(
        ChannelMember.channel_id == message.channel_id,
        ChannelMember.user_id == user_id
    )
    membership_result = await db.execute(membership_query)
    if not membership_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="You must be a channel member to react")
    
    # Get user info for realtime event
    user_query = select(User).where(User.id == user_id)
    user_result = await db.execute(user_query)
    user = user_result.scalar_one_or_none()
    username = user.username if user else f"user_{user_id}"
    
    # Check if reaction already exists
    existing_query = select(MessageReaction).where(
        MessageReaction.message_id == message_id,
        MessageReaction.user_id == user_id,
        MessageReaction.emoji == emoji,
    )
    existing_result = await db.execute(existing_query)
    existing_reaction = existing_result.scalar_one_or_none()
    
    action = None
    
    if existing_reaction:
        # Remove reaction (toggle off)
        await db.delete(existing_reaction)
        action = "removed"
        
        # Audit log
        audit = AuditLog(
            user_id=user_id,
            action="message.reaction.removed",
            target_type="message",
            target_id=message_id,
            meta=json.dumps({
                "emoji": emoji,
                "channel_id": message.channel_id,
            }),
        )
        db.add(audit)
        
    else:
        # Add reaction (toggle on)
        reaction = MessageReaction(
            message_id=message_id,
            user_id=user_id,
            emoji=emoji,
        )
        db.add(reaction)
        action = "added"
        
        # Audit log
        audit = AuditLog(
            user_id=user_id,
            action="message.reaction.added",
            target_type="message",
            target_id=message_id,
            meta=json.dumps({
                "emoji": emoji,
                "channel_id": message.channel_id,
            }),
        )
        db.add(audit)
    
    await db.commit()
    
    # Get updated reaction summary
    reactions_query = select(MessageReaction).where(MessageReaction.message_id == message_id)
    reactions_result = await db.execute(reactions_query)
    all_reactions = reactions_result.scalars().all()
    
    # Group by emoji
    reaction_map = {}
    for r in all_reactions:
        if r.emoji not in reaction_map:
            reaction_map[r.emoji] = {"emoji": r.emoji, "count": 0, "users": []}
        reaction_map[r.emoji]["count"] += 1
        reaction_map[r.emoji]["users"].append(r.user_id)
    
    reactions_list = list(reaction_map.values())
    
    # Emit realtime event
    try:
        from app.realtime.socket import emit_reaction_added, emit_reaction_removed
        
        reaction_data = {
            "message_id": message_id,
            "emoji": emoji,
            "user_id": user_id,
            "username": username,
        }
        
        if action == "added":
            await emit_reaction_added(message.channel_id, reaction_data)
        else:
            await emit_reaction_removed(message.channel_id, reaction_data)
            
    except Exception as e:
        logger.warning(f"Failed to emit reaction event: {e}")
    
    return ReactionToggleResponse(
        action=action,
        emoji=emoji,
        message_id=message_id,
        reactions=reactions_list
    )


@router.delete("/{message_id}/reactions/{emoji}")
async def remove_reaction(
    message_id: int,
    emoji: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Explicitly remove a reaction (DELETE endpoint).
    
    Note: The POST toggle endpoint is preferred for consistency,
    but this DELETE endpoint is kept for REST compliance.
    """
    import json
    from app.db.models import ChannelMember
    
    user_id = current_user["user_id"]
    
    # URL decode emoji (in case it was encoded)
    from urllib.parse import unquote
    emoji = unquote(emoji).strip()
    
    if not emoji:
        raise HTTPException(status_code=400, detail="Emoji cannot be empty")
    
    # Verify message exists
    msg_query = select(Message).where(Message.id == message_id)
    msg_result = await db.execute(msg_query)
    message = msg_result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    # Find the reaction
    query = select(MessageReaction).where(
        MessageReaction.message_id == message_id,
        MessageReaction.user_id == user_id,
        MessageReaction.emoji == emoji,
    )
    result = await db.execute(query)
    reaction = result.scalar_one_or_none()
    
    if not reaction:
        raise HTTPException(status_code=404, detail="Reaction not found")
    
    # Get user info for realtime event
    user_query = select(User).where(User.id == user_id)
    user_result = await db.execute(user_query)
    user = user_result.scalar_one_or_none()
    username = user.username if user else f"user_{user_id}"
    
    await db.delete(reaction)
    
    # Audit log
    audit = AuditLog(
        user_id=user_id,
        action="message.reaction.removed",
        target_type="message",
        target_id=message_id,
        meta=json.dumps({
            "emoji": emoji,
            "channel_id": message.channel_id,
        }),
    )
    db.add(audit)
    
    await db.commit()
    
    # Emit realtime event
    try:
        from app.realtime.socket import emit_reaction_removed
        
        reaction_data = {
            "message_id": message_id,
            "emoji": emoji,
            "user_id": user_id,
            "username": username,
        }
        await emit_reaction_removed(message.channel_id, reaction_data)
        
    except Exception as e:
        logger.warning(f"Failed to emit reaction removed event: {e}")
    
    return {"message": "Reaction removed", "emoji": emoji}


class SearchRequest(BaseModel):
    query: str
    channel_id: Optional[int] = None
    user_id: Optional[int] = None
    limit: int = 50


class SearchResult(BaseModel):
    id: int
    content: str
    channel_id: int
    channel_name: Optional[str] = None
    author_id: int
    author_username: Optional[str] = None
    created_at: datetime
    highlight: Optional[str] = None


@router.post("/search", response_model=List[SearchResult])
async def search_messages(
    request: SearchRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Search messages with optional filters."""
    search_term = f"%{request.query}%"
    
    # Build base query with joins
    query = (
        select(Message, User.username, Channel.name)
        .join(User, Message.author_id == User.id)
        .join(Channel, Message.channel_id == Channel.id)
        .where(
            Message.content.ilike(search_term),
            Message.is_deleted == False
        )
    )
    
    # Apply optional filters
    if request.channel_id:
        query = query.where(Message.channel_id == request.channel_id)
    
    if request.user_id:
        query = query.where(Message.author_id == request.user_id)
    
    query = query.order_by(desc(Message.created_at)).limit(request.limit)
    
    result = await db.execute(query)
    rows = result.all()
    
    # Create highlighted snippets
    search_results = []
    for msg, username, channel_name in rows:
        # Create simple highlight by finding the match position
        content = msg.content
        lower_content = content.lower()
        lower_query = request.query.lower()
        idx = lower_content.find(lower_query)
        
        if idx >= 0:
            # Extract snippet around match (50 chars before/after)
            start = max(0, idx - 50)
            end = min(len(content), idx + len(request.query) + 50)
            snippet = content[start:end]
            if start > 0:
                snippet = "..." + snippet
            if end < len(content):
                snippet = snippet + "..."
            highlight = snippet
        else:
            highlight = content[:100] + ("..." if len(content) > 100 else "")
        
        search_results.append(SearchResult(
            id=msg.id,
            content=msg.content,
            channel_id=msg.channel_id,
            channel_name=channel_name,
            author_id=msg.author_id,
            author_username=username,
            created_at=msg.created_at,
            highlight=highlight,
        ))
    
    return search_results
