from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, update, desc
from pydantic import BaseModel
from typing import Optional, List, Literal
from datetime import datetime, timezone
import uuid

from app.db.database import get_db
from app.db.models import Channel, ChannelMember, ChannelType, Team, FileAttachment, AuditLog, User
from app.core.security import get_current_user, require_admin
from app.api.ws import manager as ws_manager
from app.storage.minio_client import get_minio_storage
from app.core.config import settings
from app.permissions.constants import Permission
from app.permissions.dependencies import require_permission

router = APIRouter()


def _to_aware(dt):
    """Return a timezone-aware datetime in UTC, or None if dt is None.

    - If `dt` is naive, attach UTC tzinfo (dt.replace(tzinfo=timezone.utc)).
    - If `dt` is already timezone-aware, return as-is.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class ChannelCreateRequest(BaseModel):
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    type: str = "public"
    team_id: Optional[int] = None


class ChannelResponse(BaseModel):
    id: int
    name: str
    display_name: Optional[str]
    description: Optional[str]
    type: str
    team_id: Optional[int]
    last_activity_at: Optional[str] = None
    unread_count: int = 0

    class Config:
        from_attributes = True


@router.post("", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
async def create_channel(
    request: ChannelCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Require admin privileges to create channels
    await require_admin(db, current_user)

    # If team_id provided, verify team exists
    if request.team_id:
        query = select(Team).where(Team.id == request.team_id)
        result = await db.execute(query)
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Team not found")
    # Accept short types (Mattermost style) "O" (open/public) and "P" (private)
    # Use the raw dict value to avoid Pydantic coercion to enums which can raise on short codes like 'O'/'P'
    t = request.dict().get('type', 'public')
    if t in ("O", "o"):
        channel_type = ChannelType.public.value
    elif t in ("P", "p"):
        channel_type = ChannelType.private.value
    else:
        # fall back to provided keyword or default
        try:
            channel_type = ChannelType(t).value
        except Exception:
            channel_type = ChannelType.public.value

    channel = Channel(
        name=request.name,
        display_name=request.display_name or request.name,
        description=request.description,
        type=channel_type,
        team_id=request.team_id,
    )
    db.add(channel)
    await db.commit()
    await db.refresh(channel)
    
    # Add creator as member
    membership = ChannelMember(
        user_id=current_user["user_id"],
        channel_id=channel.id,
    )
    db.add(membership)
    await db.commit()
    
    # Broadcast channel_created to presence subscribers so sidebar can update live
    try:
        await ws_manager.broadcast_presence({
            "type": "channel_created",
            "channel": {
                "id": channel.id,
                "name": channel.name,
                "display_name": channel.display_name,
                "description": channel.description,
                "type": channel.type,
                "team_id": channel.team_id,
            }
        })
    except Exception:
        # Do not fail create on websocket broadcast errors — log and continue
        import logging
        logging.exception('Failed to broadcast channel_created')
    
    return channel


@router.get("/", response_model=List[ChannelResponse])
async def list_channels(
    team_id: Optional[int] = None,
    include_dms: bool = False,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Use a local import so we don't change top-level imports
    from sqlalchemy import exists

    # Visibility rules:
    # - Public channels: always visible
    # - Private channels: visible only if current user is a ChannelMember
    # - Direct channels: never included in this listing (handled separately via include_dms)
    if team_id:
        query = select(Channel).where(
            Channel.team_id == team_id,
            or_(
                Channel.type == ChannelType.public,
                and_(
                    Channel.type == ChannelType.private,
                    exists().where(
                        ChannelMember.channel_id == Channel.id,
                        ChannelMember.user_id == current_user["user_id"]
                    )
                )
            )
        )
    elif include_dms:
        # Get DM channels where user is a member, but exclude ones that have been migrated
        from app.db.models import LegacyDMMigration
        dm_query = (
            select(Channel)
            .join(ChannelMember, Channel.id == ChannelMember.channel_id)
            .outerjoin(LegacyDMMigration, LegacyDMMigration.legacy_channel_id == Channel.id)
            .where(
                ChannelMember.user_id == current_user["user_id"],
                Channel.type == ChannelType.direct,
                or_(LegacyDMMigration.migrated.is_(False), LegacyDMMigration.id.is_(None))
            )
        )
        result = await db.execute(dm_query)
        return result.scalars().all()
    else:
        query = select(Channel).where(
            Channel.team_id.is_(None),
            or_(
                Channel.type == ChannelType.public,
                and_(
                    Channel.type == ChannelType.private,
                    exists().where(
                        ChannelMember.channel_id == Channel.id,
                        ChannelMember.user_id == current_user["user_id"]
                    )
                )
            )
        )
    
    # Order channels in SQL by last activity (newest first). Use a correlated scalar subquery
    # so the DB is authoritative for ordering and we avoid Python comparisons of datetimes.
    from app.db.models import Message

    # Execute channel query ordered by last_activity (NULLs last)
    last_activity_expr = (
        select(func.max(func.coalesce(Message.last_activity_at, Message.created_at)))
        .where(Message.channel_id == Channel.id, Message.is_deleted == False, Message.parent_id.is_(None))
        .scalar_subquery()
    )

    query = query.order_by(desc(last_activity_expr).nulls_last())
    result = await db.execute(query)
    channels = result.scalars().all()

    enriched = []
    for ch in channels:
        # Retrieve last_activity_at for this channel (same logic as the ordering subquery)
        last_q = select(func.max(func.coalesce(Message.last_activity_at, Message.created_at))).where(
            Message.channel_id == ch.id,
            Message.is_deleted == False,
            Message.parent_id.is_(None)
        )
        last_res = await db.execute(last_q)
        last_val = _to_aware(last_res.scalar_one_or_none())
        last_iso = last_val.isoformat() if last_val else None

        # Compute unread count entirely in SQL. If ChannelMember.last_read_at IS NULL,
        # count all messages; otherwise count messages where created_at > last_read_at.
        cm = ChannelMember
        unread_q = (
            select(func.count(Message.id))
            .select_from(Message)
            .outerjoin(cm, and_(cm.channel_id == ch.id, cm.user_id == current_user["user_id"]))
            .where(
                Message.channel_id == ch.id,
                Message.is_deleted == False,
                or_(cm.last_read_at.is_(None), Message.created_at > cm.last_read_at),
            )
        )
        unread_res = await db.execute(unread_q)
        unread = unread_res.scalar_one() or 0

        enriched.append({
            "id": ch.id,
            "name": ch.name,
            "display_name": ch.display_name,
            "description": ch.description,
            "type": ch.type,
            "team_id": ch.team_id,
            "last_activity_at": last_iso,
            "unread_count": int(unread or 0),
        })

    return enriched


class DMCreateRequest(BaseModel):
    user_id: int


class DMChannelResponse(BaseModel):
    id: int
    name: str
    display_name: Optional[str]
    type: str
    other_user_id: int
    other_username: str

    class Config:
        from_attributes = True


@router.post("/direct", response_model=DMChannelResponse)
async def create_or_get_dm_channel(
    request: DMCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create or get an existing DM channel between current user and target user."""
    target_user_id = request.user_id
    my_user_id = current_user["user_id"]
    
    if target_user_id == my_user_id:
        raise HTTPException(status_code=400, detail="Cannot create DM with yourself")
    
    # Verify target user exists
    user_query = select(User).where(User.id == target_user_id)
    user_result = await db.execute(user_query)
    target_user = user_result.scalar_one_or_none()
    
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if DM channel already exists between these two users
    # A DM channel has exactly 2 members: current user and target user
    existing_dm_query = (
        select(Channel)
        .join(ChannelMember, Channel.id == ChannelMember.channel_id)
        .where(Channel.type == ChannelType.direct)
        .where(ChannelMember.user_id.in_([my_user_id, target_user_id]))
        .group_by(Channel.id)
    )
    result = await db.execute(existing_dm_query)
    potential_channels = result.scalars().all()
    
    # Find a channel that has both users as members
    for channel in potential_channels:
        members_query = select(ChannelMember.user_id).where(ChannelMember.channel_id == channel.id)
        members_result = await db.execute(members_query)
        member_ids = set(members_result.scalars().all())
        
        if member_ids == {my_user_id, target_user_id}:
            # Found existing DM channel
            return {
                "id": channel.id,
                "name": channel.name,
                "display_name": channel.display_name,
                "type": channel.type,
                "other_user_id": target_user_id,
                "other_username": target_user.username,
            }
    
    # Create new DM channel
    channel_name = f"dm-{min(my_user_id, target_user_id)}-{max(my_user_id, target_user_id)}"
    channel = Channel(
        name=channel_name,
        display_name=target_user.display_name or target_user.username,
        type=ChannelType.direct.value,
    )
    db.add(channel)
    await db.flush()  # Get the channel ID
    
    # Add both users as members
    membership1 = ChannelMember(user_id=my_user_id, channel_id=channel.id)
    membership2 = ChannelMember(user_id=target_user_id, channel_id=channel.id)
    db.add(membership1)
    db.add(membership2)
    await db.commit()
    
    return {
        "id": channel.id,
        "name": channel.name,
        "display_name": channel.display_name,
        "type": channel.type,
        "other_user_id": target_user_id,
        "other_username": target_user.username,
    }


@router.get("/direct/list", response_model=List[DMChannelResponse])
async def list_dm_channels(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all DM channels for the current user."""
    my_user_id = current_user["user_id"]
    
    # Get all DM channels where user is a member, exclude migrated legacy DMs
    from app.db.models import LegacyDMMigration
    dm_query = (
        select(Channel)
        .join(ChannelMember, Channel.id == ChannelMember.channel_id)
        .outerjoin(LegacyDMMigration, LegacyDMMigration.legacy_channel_id == Channel.id)
        .where(
            ChannelMember.user_id == my_user_id,
            Channel.type == ChannelType.direct,
            or_(LegacyDMMigration.migrated.is_(False), LegacyDMMigration.id.is_(None))
        )
    )
    result = await db.execute(dm_query)
    dm_channels = result.scalars().all()
    
    # For each channel, find the other user
    dm_list = []
    for channel in dm_channels:
        try:
            # Get the other member (use .first() to handle duplicates gracefully)
            other_member_query = (
                select(ChannelMember)
                .where(
                    ChannelMember.channel_id == channel.id,
                    ChannelMember.user_id != my_user_id
                )
                .limit(1)
            )
            other_result = await db.execute(other_member_query)
            other_member = other_result.scalar_one_or_none()
            
            if other_member:
                # Get the other user's info
                user_query = select(User).where(User.id == other_member.user_id)
                user_result = await db.execute(user_query)
                other_user = user_result.scalar_one_or_none()
                
                if other_user:
                    dm_list.append({
                        "id": channel.id,
                        "name": channel.name,
                        "display_name": other_user.display_name or other_user.username,
                        "type": channel.type,
                        "other_user_id": other_user.id,
                        "other_username": other_user.username,
                    })
        except Exception:
            # Skip channels that can't be processed
            continue
    
    return dm_list


@router.get("/{channel_id}", response_model=ChannelResponse)
async def get_channel(
    channel_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Channel).where(Channel.id == channel_id)
    result = await db.execute(query)
    channel = result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    return channel


class MarkReadRequest(BaseModel):
    """Request body for marking a channel as read."""
    last_read_message_id: Optional[int] = None  # Phase 4.4 - message-based read receipts


@router.post("/{channel_id}/read")
async def mark_channel_read(
    channel_id: int,
    request: Optional[MarkReadRequest] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Mark a channel as read.
    
    Phase 4.4: If last_read_message_id is provided, uses efficient message-based tracking.
    Otherwise falls back to timestamp-based tracking.
    """
    # Validate channel exists
    query = select(Channel).where(Channel.id == channel_id)
    result = await db.execute(query)
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Validate membership
    from app.db.crud import get_channel_member
    membership = await get_channel_member(db, channel_id, current_user["user_id"])
    if not membership:
        raise HTTPException(status_code=403, detail="You are not a member of this channel. Contact admin if that is not the case.")

    user_id = current_user["user_id"]
    
    # Phase 4.4: Message-based read receipts
    if request and request.last_read_message_id:
        from app.db.models import ChannelRead, Message
        from app.api.ws import manager

        # Verify message exists and belongs to this channel
        msg_query = select(Message).where(
            Message.id == request.last_read_message_id,
            Message.channel_id == channel_id
        )
        msg_result = await db.execute(msg_query)
        msg = msg_result.scalar_one_or_none()
        if not msg:
            raise HTTPException(status_code=404, detail="Message not found in this channel")

        # Upsert channel read
        read_query = select(ChannelRead).where(
            ChannelRead.user_id == user_id,
            ChannelRead.channel_id == channel_id
        )
        read_result = await db.execute(read_query)
        channel_read = read_result.scalar_one_or_none()

        should_emit = False

        if channel_read:
            # Only update if new message_id is greater
            if channel_read.last_read_message_id is None or request.last_read_message_id > channel_read.last_read_message_id:
                channel_read.last_read_message_id = request.last_read_message_id
                db.add(channel_read)
                should_emit = True
        else:
            # Create new record
            channel_read = ChannelRead(
                user_id=user_id,
                channel_id=channel_id,
                last_read_message_id=request.last_read_message_id
            )
            db.add(channel_read)
            should_emit = True

        # Also update ChannelMember.last_read_at to now (Slack-style)
        try:
            await db.execute(
                update(ChannelMember)
                .where(ChannelMember.channel_id == channel_id, ChannelMember.user_id == user_id)
                .values(last_read_at=func.now())
            )
        except Exception:
            pass

        await db.commit()

        # Emit receipt:update via Socket.IO
        if should_emit:
            try:
                from app.realtime.socket import emit_receipt_update
                await emit_receipt_update(
                    channel_id=channel_id,
                    user_id=user_id,
                    last_read_message_id=request.last_read_message_id,
                    skip_user_id=user_id
                )
            except Exception:
                import logging
                logging.exception("Failed to emit receipt:update")

        # Also send an unread_update (zero) to the user so UI can refresh
        try:
            await manager.send_to_user(user_id, {
                "type": "unread_update",
                "channel_id": channel_id,
                "unread_count": 0,
            })
        except Exception:
            pass

        return {"ok": True}

    # Legacy: Timestamp-based tracking — perform UPDATE at the DB level so the
    # stored `last_read_at` is set to the DB current timestamp (timezone-aware)
    await db.execute(
        update(ChannelMember)
        .where(ChannelMember.channel_id == channel_id, ChannelMember.user_id == current_user["user_id"])
        .values(last_read_at=func.now())
    )
    await db.commit()

    # Re-fetch membership so we can return the updated last_read_at value
    from app.db.crud import get_channel_member
    membership = await get_channel_member(db, channel_id, current_user["user_id"])

    # Emit unread_update with zero for this user
    try:
        from app.api.ws import manager
        await manager.send_to_user(current_user["user_id"], {
            "type": "unread_update",
            "channel_id": channel_id,
            "unread_count": 0,
        })
    except Exception:
        pass

    return {
        "channel_id": channel_id,
        "last_read_at": membership.last_read_at.isoformat() if membership and membership.last_read_at else None
    }


class ChannelReadResponse(BaseModel):
    """Response for channel read receipt."""
    user_id: int
    last_read_message_id: Optional[int]

    class Config:
        from_attributes = True


@router.get("/{channel_id}/reads", response_model=List[ChannelReadResponse])
async def get_channel_reads(
    channel_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all read receipts for a channel.
    Phase 4.4 - Returns list of {user_id, last_read_message_id} for computing "Seen by X".
    """
    # Validate channel exists
    query = select(Channel).where(Channel.id == channel_id)
    result = await db.execute(query)
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Get all read receipts for this channel
    from app.db.models import ChannelRead
    reads_query = select(ChannelRead).where(ChannelRead.channel_id == channel_id)
    reads_result = await db.execute(reads_query)
    reads = reads_result.scalars().all()
    
    return [
        {"user_id": r.user_id, "last_read_message_id": r.last_read_message_id}
        for r in reads
    ]


@router.post("/{channel_id}/join")
async def join_channel(
    channel_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Check channel exists
    query = select(Channel).where(Channel.id == channel_id)
    result = await db.execute(query)
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Prevent users with must_change_password from joining
    result = await db.execute(select(User).where(User.id == current_user["user_id"]))
    user = result.scalar_one_or_none()
    if user and getattr(user, 'must_change_password', False):
        raise HTTPException(status_code=403, detail="Password change required")

    # For private channels, do not allow self-join via REST; require admin
    if channel.type != 'public':
        raise HTTPException(status_code=403, detail="You are not a member of this channel. Contact admin if that is not the case.")

    # Check if already a member
    query = select(ChannelMember).where(
        ChannelMember.channel_id == channel_id,
        ChannelMember.user_id == current_user["user_id"]
    )
    result = await db.execute(query)
    if result.scalar_one_or_none():
        return {"message": "Already a member of this channel"}

    membership = ChannelMember(
        user_id=current_user["user_id"],
        channel_id=channel_id,
    )
    db.add(membership)
    await db.commit()
    
    return {"message": "Successfully joined channel"}


@router.get("/{channel_id}/messages")
async def get_channel_messages_v34(
    channel_id: int,
    limit: int = 50,
    before: Optional[int] = None,  # message ID cursor
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """U3.4: Read-only message list with cursor (before) pagination.

    - Enforce membership: user must be a member of the channel
    - Accepts `limit` (default 50, max 100) and `before` (message id cursor)
    - Returns messages ordered ascending by created_at and `has_more` flag
    """
    # Validate channel exists
    query = select(Channel).where(Channel.id == channel_id)
    result = await db.execute(query)
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Enforce membership for non-public channels
    from app.db.crud import get_channel_member
    membership = await get_channel_member(db, channel_id, current_user["user_id"])
    if channel.type != 'public' and not membership:
        # If this is a DM, provide a participant-specific message
        ch_candidates = set()
        try:
            if hasattr(channel.type, 'value'):
                ch_candidates.add(channel.type.value)
        except Exception:
            pass
        try:
            ch_candidates.add(str(channel.type))
        except Exception:
            pass
        try:
            ch_candidates.add(channel.type)
        except Exception:
            pass
        from app.db.enums import ChannelType as _CT
        if _CT.direct.value in ch_candidates:
            raise HTTPException(status_code=403, detail="You are not a participant in this direct conversation.")

        raise HTTPException(status_code=403, detail="You are not a member of this channel. Contact admin if that is not the case.")

    # Normalize limit and prepare cursor
    limit = min(max(1, limit), 100)
    from app.db.models import Message
    from sqlalchemy.orm import selectinload
    from sqlalchemy import desc

    cursor_time = None
    cursor_created_at = None
    if before is not None:
        # Look up the message to get its last_activity_at (fallback to created_at)
        m_q = select(Message).where(Message.id == before)
        m_r = await db.execute(m_q)
        m_obj = m_r.scalar_one_or_none()
        if m_obj:
            cursor_time = _to_aware(m_obj.last_activity_at or m_obj.created_at)
            cursor_created_at = _to_aware(m_obj.created_at)

    # Fetch messages in descending order by activity (newest activity first) with limit+1 to determine has_more
    base_q = (
        select(Message)
        .options(selectinload(Message.author), selectinload(Message.reactions), selectinload(Message.attachments))
        .where(Message.channel_id == channel_id, Message.is_deleted == False, Message.parent_id.is_(None))
    )

    if cursor_time is not None:
        # Use last_activity_at + created_at tie-breaker to keep cursor deterministic
        base_q = base_q.where(
            or_(
                Message.last_activity_at < cursor_time,
                and_(
                    Message.last_activity_at == cursor_time,
                    Message.created_at < cursor_created_at
                )
            )
        )

    # Apply public/member lower bound to avoid showing messages older than join/user creation
    # Fetch user to apply must_change_password check and lower bound
    result = await db.execute(select(User).where(User.id == current_user["user_id"]))
    user = result.scalar_one_or_none()
    if user and getattr(user, 'must_change_password', False):
        raise HTTPException(status_code=403, detail="Password change required")

    # Determine join timestamp
    join_timestamp = membership.created_at if membership else (user.created_at if user else None)
    # Apply join lower-bound only when a cursor is supplied (do not filter initial page)
    if join_timestamp and before is not None:
        base_q = base_q.where(Message.created_at >= join_timestamp)

    base_q = base_q.order_by(desc(Message.last_activity_at), desc(Message.created_at)).limit(limit + 1)

    result = await db.execute(base_q)
    rows = result.scalars().all()

    has_more = len(rows) > limit
    # keep only 'limit' newest from the fetched set and reverse to chronological order
    rows = rows[:limit]
    rows.reverse()

    # Get reply counts for each message (avoid N+1)
    message_ids = [m.id for m in rows]
    reply_counts = {}
    if message_ids:
        from sqlalchemy import func
        reply_query = (
            select(Message.parent_id, func.count(Message.id))
            .where(Message.parent_id.in_(message_ids), Message.is_deleted == False)
            .group_by(Message.parent_id)
        )
        reply_result = await db.execute(reply_query)
        reply_counts = dict(reply_result.all())

    # Transform responses using existing helper to ensure consistent shape
    from app.api.messages import transform_message_to_response

    msgs = [transform_message_to_response(m, reply_count=reply_counts.get(m.id, 0)) for m in rows]

    return {"channel_id": channel_id, "messages": msgs, "has_more": has_more}


@router.post("/{channel_id}/leave")
async def leave_channel(
    channel_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(ChannelMember).where(
        ChannelMember.channel_id == channel_id,
        ChannelMember.user_id == current_user["user_id"]
    )
    result = await db.execute(query)
    membership = result.scalar_one_or_none()
    
    if not membership:
        raise HTTPException(status_code=400, detail="You are not a member of this channel. Contact admin if that is not the case.")
    
    await db.delete(membership)
    await db.commit()
    
    return {"message": "Successfully left channel"}


class FileResponse(BaseModel):
    id: int
    filename: str
    file_path: str
    file_size: Optional[int]
    mime_type: Optional[str]
    user_id: int
    channel_id: int
    created_at: datetime
    download_url: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("/{channel_id}/files", response_model=List[FileResponse])
async def list_channel_files(
    channel_id: int,
    skip: int = 0,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all files uploaded to a channel."""
    query = (
        select(FileAttachment)
        .where(FileAttachment.channel_id == channel_id)
        .order_by(FileAttachment.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    files = result.scalars().all()
    
    # Add download URLs
    file_responses = []
    for f in files:
        try:
            storage = get_minio_storage()
            download_url = storage.get_presigned_url(f.file_path) if storage else None
        except Exception:
            download_url = None
        
        file_responses.append(FileResponse(
            id=f.id,
            filename=f.filename,
            file_path=f.file_path,
            file_size=f.file_size,
            mime_type=f.mime_type,
            user_id=f.user_id,
            channel_id=f.channel_id,
            created_at=f.created_at,
            download_url=download_url,
        ))
    
    return file_responses


@router.post("/{channel_id}/files", response_model=FileResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    channel_id: int,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload a file to a channel."""
    # Verify channel exists
    query = select(Channel).where(Channel.id == channel_id)
    result = await db.execute(query)
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Stream file content and enforce size limit to avoid loading whole file into memory
    import tempfile

    MAX_BYTES = settings.MAX_UPLOAD_MB * 1024 * 1024

    print(f"[UPLOAD] receiving file {file.filename}; configured MAX_UPLOAD_MB={settings.MAX_UPLOAD_MB}")

    # Write to temporary file while checking size
    total = 0
    with tempfile.TemporaryFile() as tmp:
        chunk_size = 64 * 1024
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            tmp.write(chunk)
            total += len(chunk)
            if total > MAX_BYTES:
                print(f"[UPLOAD] rejected (size limit) {file.filename} {total} bytes")
                raise HTTPException(status_code=413, detail="File exceeds maximum size of 50MB")

        tmp.seek(0)
        file_size = total

        print(f"[UPLOAD] MAX_BYTES={MAX_BYTES}, final_size={file_size}")
        # Log received file name + size (accepted)
        print(f"[UPLOAD] received {file.filename} {file_size}")

        # Generate unique filename
        ext = file.filename.split(".")[-1] if "." in file.filename else ""
        unique_filename = f"{channel_id}/{uuid.uuid4()}.{ext}" if ext else f"{channel_id}/{uuid.uuid4()}"

        # Upload to MinIO using streaming helper
        try:
            storage = get_minio_storage()
            file_path = await storage.upload_file_stream(
                tmp,
                file_size,
                unique_filename,
                file.content_type or "application/octet-stream"
            ) if storage else None
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")
    
    # Save to database
    file_attachment = FileAttachment(
        channel_id=channel_id,
        user_id=current_user["user_id"],
        filename=file.filename,
        file_path=file_path,
        file_size=file_size,
        mime_type=file.content_type,
    )
    db.add(file_attachment)
    
    # Audit log
    import json
    audit = AuditLog(
        user_id=current_user["user_id"],
        action="file_upload",
        target_type="channel",
        target_id=channel_id,
        meta=json.dumps({"filename": file.filename, "size": file_size}),
    )
    db.add(audit)
    
    await db.commit()
    await db.refresh(file_attachment)
    
    # Get download URL
    try:
        storage = get_minio_storage()
        download_url = storage.get_presigned_url(file_path) if storage else None
    except Exception:
        download_url = None
    
    return FileResponse(
        id=file_attachment.id,
        filename=file_attachment.filename,
        file_path=file_attachment.file_path,
        file_size=file_attachment.file_size,
        mime_type=file_attachment.mime_type,
        user_id=file_attachment.user_id,
        channel_id=file_attachment.channel_id,
        created_at=file_attachment.created_at,
        download_url=download_url,
    )


@router.delete("/{channel_id}/files/{file_id}")
async def delete_file(
    channel_id: int,
    file_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a file from a channel."""
    query = select(FileAttachment).where(
        FileAttachment.id == file_id,
        FileAttachment.channel_id == channel_id,
    )
    result = await db.execute(query)
    file_attachment = result.scalar_one_or_none()
    
    if not file_attachment:
        raise HTTPException(status_code=404, detail="File not found")
    
    if file_attachment.user_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Can only delete your own files")
    
    # Delete from MinIO
    try:
        storage = get_minio_storage()
        if storage:
            await storage.delete_file(file_attachment.file_path)
    except Exception:
        pass  # File might not exist in storage
    
    await db.delete(file_attachment)
    await db.commit()
    
    return {"message": "File deleted"}


@router.get("/{channel_id}/files/{file_id}/download")
async def download_file(
    channel_id: int,
    file_id: int,
    token: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Download a file from a channel - proxies through backend to avoid exposing MinIO.
    
    Accepts token either via Authorization header or as query parameter for direct link access.
    """
    from fastapi.responses import Response
    from app.core.security import decode_token
    
    # Token can be passed as query param for direct link downloads
    if not token:
        raise HTTPException(status_code=401, detail="Token required. Add ?token=YOUR_TOKEN to the URL")
    
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    query = select(FileAttachment).where(
        FileAttachment.id == file_id,
        FileAttachment.channel_id == channel_id,
    )
    result = await db.execute(query)
    file_attachment = result.scalar_one_or_none()
    
    if not file_attachment:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Download from MinIO
    try:
        storage = get_minio_storage()
        file_content = await storage.download_file(file_attachment.file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")
    
    return Response(
        content=file_content,
        media_type=file_attachment.mime_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{file_attachment.filename}"'
        }
    )


# Channel Member Management


class ChannelMemberResponse(BaseModel):
    id: int
    user_id: int
    channel_id: int
    username: str
    display_name: Optional[str] = None
    role: str = "member"  # admin or member
    
    class Config:
        from_attributes = True


class AddMemberRequest(BaseModel):
    user_id: int


class UpdateMemberRoleRequest(BaseModel):
    role: str  # admin or member


@router.get("/{channel_id}/members", response_model=List[ChannelMemberResponse])
async def list_channel_members(
    channel_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all members of a channel."""
    # Verify channel exists
    channel_query = select(Channel).where(Channel.id == channel_id)
    channel_result = await db.execute(channel_query)
    channel = channel_result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Get members with user info
    query = (
        select(ChannelMember, User)
        .join(User, ChannelMember.user_id == User.id)
        .where(ChannelMember.channel_id == channel_id)
    )
    result = await db.execute(query)
    rows = result.all()
    
    members = []
    for member, user in rows:
        members.append(ChannelMemberResponse(
            id=member.id,
            user_id=user.id,
            channel_id=channel_id,
            username=user.username,
            display_name=user.display_name,
            role="admin" if user.is_system_admin else "member"
        ))
    
    return members


@router.post(
    "/{channel_id}/members",
    response_model=ChannelMemberResponse,
)
async def add_channel_member(
    channel_id: int,
    request: AddMemberRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Add a user to a channel. Admins only."""
    # Verify channel exists and is not a DM
    channel_query = select(Channel).where(Channel.id == channel_id)
    channel_result = await db.execute(channel_query)
    channel = channel_result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    channel_type_val = channel.type.value if hasattr(channel.type, 'value') else channel.type
    if channel_type_val == ChannelType.direct.value:
        raise HTTPException(status_code=403, detail="Direct messages cannot be managed as channels.")

    # Enforce admin-only management
    user_q = select(User).where(User.id == current_user["user_id"])
    user_r = await db.execute(user_q)
    curr_user = user_r.scalar_one_or_none()
    role_val = None
    if curr_user:
        try:
            role_val = curr_user.role.value if hasattr(curr_user.role, 'value') else curr_user.role
        except Exception:
            role_val = getattr(curr_user, 'role', None)

    if not (getattr(curr_user, 'is_system_admin', False) or role_val == 'team_admin' or role_val == 'system_admin'):
        raise HTTPException(status_code=403, detail="You do not have permission to manage this channel.")
    
    # Check if target user exists
    user_query = select(User).where(User.id == request.user_id)
    user_result = await db.execute(user_query)
    target_user = user_result.scalar_one_or_none()
    
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if already a member
    existing_query = select(ChannelMember).where(
        ChannelMember.channel_id == channel_id,
        ChannelMember.user_id == request.user_id
    )
    existing_result = await db.execute(existing_query)
    if existing_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User is already a member")
    
    # Add membership
    membership = ChannelMember(
        user_id=request.user_id,
        channel_id=channel_id
    )
    db.add(membership)
    await db.commit()
    await db.refresh(membership)
    
    return ChannelMemberResponse(
        id=membership.id,
        user_id=target_user.id,
        channel_id=channel_id,
        username=target_user.username,
        display_name=target_user.display_name,
        role="member"
    )


async def _disallow_dm_management(channel_id: int, db: AsyncSession = Depends(get_db)):
    """Dependency to reject any management actions against DM channels before other permissions run."""
    query = select(Channel).where(Channel.id == channel_id)
    result = await db.execute(query)
    channel = result.scalar_one_or_none()
    if channel:
        channel_type_val = channel.type.value if hasattr(channel.type, 'value') else channel.type
        if channel_type_val == ChannelType.direct.value:
            raise HTTPException(status_code=403, detail="Direct messages cannot be managed as channels.")


@router.delete(
    "/{channel_id}/members/{user_id}",
    dependencies=[
        Depends(_disallow_dm_management),
        Depends(
            require_permission(
                Permission.KICK_MEMBER,
                channel_param="channel_id",
            )
        )
    ],
)
async def remove_channel_member(
    channel_id: int,
    user_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Remove a user from a channel."""
    # Verify channel exists
    channel_query = select(Channel).where(Channel.id == channel_id)
    channel_result = await db.execute(channel_query)
    channel = channel_result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    channel_type_val = channel.type.value if hasattr(channel.type, 'value') else channel.type
    if channel_type_val == ChannelType.direct.value:
        raise HTTPException(status_code=403, detail="Direct messages cannot be managed as channels.")    
    # Enforce admin-only removal
    current_user_query = select(User).where(User.id == current_user["user_id"])
    current_user_result = await db.execute(current_user_query)
    curr_user = current_user_result.scalar_one_or_none()
    role_val = None
    if curr_user:
        try:
            role_val = curr_user.role.value if hasattr(curr_user.role, 'value') else curr_user.role
        except Exception:
            role_val = getattr(curr_user, 'role', None)

    if not (getattr(curr_user, 'is_system_admin', False) or role_val == 'team_admin' or role_val == 'system_admin'):
        raise HTTPException(status_code=403, detail="You do not have permission to manage this channel.")
    
    # Find and remove membership
    member_query = select(ChannelMember).where(
        ChannelMember.channel_id == channel_id,
        ChannelMember.user_id == user_id
    )
    member_result = await db.execute(member_query)
    membership = member_result.scalar_one_or_none()
    
    if not membership:
        raise HTTPException(status_code=404, detail="You are not a member of this channel. Contact admin if that is not the case.")
    
    await db.delete(membership)
    await db.commit()
    
    return {"message": "User removed from channel"}
