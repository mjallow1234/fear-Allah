from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from app.db.database import get_db
from app.db.models import DirectConversation, DirectConversationParticipant, DirectConversationRead, User, Message
from app.core.security import get_current_user, check_user_can_post
from app.realtime.socket import emit_message_new, emit_direct_read_updated
from app.api.ws import manager
from app.api.messages import transform_message_to_response
from datetime import datetime
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


class CreateDirectConversationRequest(BaseModel):
    other_user_id: int


class DirectConversationResponse(BaseModel):
    id: int
    created_by_user_id: int
    participant_ids: List[int]
    created_at: datetime

    class Config:
        orm_mode = True


class DirectMessageCreateRequest(BaseModel):
    content: str
    parent_id: Optional[int] = None


@router.post("/", response_model=DirectConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_direct_conversation(
    request: CreateDirectConversationRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if request.other_user_id == current_user["user_id"]:
        raise HTTPException(status_code=400, detail="Cannot create direct conversation with yourself")

    # Check other user exists
    r = await db.execute(select(User).where(User.id == request.other_user_id))
    other = r.scalar_one_or_none()
    if not other:
        raise HTTPException(status_code=404, detail="User not found")

    # Compute canonical pair key
    a = int(current_user["user_id"]) ; b = int(request.other_user_id)
    pair_key = f"{min(a,b)}:{max(a,b)}"

    # Look for existing conversation with this pair_key
    r = await db.execute(select(DirectConversation).where(DirectConversation.participant_pair == pair_key))
    conv = r.scalar_one_or_none()
    if conv:
        # Avoid lazy-loading relationships in async context; fetch participants explicitly
        pr = await db.execute(select(DirectConversationParticipant.user_id).where(DirectConversationParticipant.direct_conversation_id == conv.id))
        participant_ids = [row[0] for row in pr.all()]
        return DirectConversationResponse(id=conv.id, created_by_user_id=conv.created_by_user_id, participant_ids=participant_ids, created_at=conv.created_at)

    # Create new conversation
    conv = DirectConversation(created_by_user_id=current_user["user_id"], participant_pair=pair_key)
    db.add(conv)
    await db.flush()

    p1 = DirectConversationParticipant(direct_conversation_id=conv.id, user_id=current_user["user_id"]) 
    p2 = DirectConversationParticipant(direct_conversation_id=conv.id, user_id=request.other_user_id)
    db.add_all([p1, p2])
    await db.commit()
    await db.refresh(conv)

    # Use the participant objects we created rather than triggering a lazy load
    participant_ids = [p1.user_id, p2.user_id]
    return DirectConversationResponse(id=conv.id, created_by_user_id=conv.created_by_user_id, participant_ids=participant_ids, created_at=conv.created_at)


@router.get("/", response_model=List[DirectConversationResponse])
async def list_direct_conversations(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from sqlalchemy.orm import selectinload

    q = select(DirectConversation).join(DirectConversation.participants).where(DirectConversationParticipant.user_id == current_user["user_id"]).options(selectinload(DirectConversation.participants))  # type: ignore
    r = await db.execute(q)
    convs = r.scalars().all()
    res = []
    for conv in convs:
        participant_ids = [p.user_id for p in conv.participants]
        res.append(DirectConversationResponse(id=conv.id, created_by_user_id=conv.created_by_user_id, participant_ids=participant_ids, created_at=conv.created_at))
    return res


@router.get("/{conv_id}/messages")
async def get_direct_conversation_messages(
    conv_id: int,
    skip: int = 0,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify membership
    r = await db.execute(select(DirectConversationParticipant).where(DirectConversationParticipant.direct_conversation_id == conv_id, DirectConversationParticipant.user_id == current_user["user_id"]))
    member = r.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=403, detail="You are not a participant in this direct conversation.")

    # join timestamp
    join_ts = member.joined_at
    import logging
    try:
        js = join_ts.isoformat() if join_ts else None
    except Exception:
        js = str(join_ts)
    logging.getLogger(__name__).info(f"member.joined_at for conv {conv_id} user {current_user['user_id']}: {js}")

    # Fetch messages for conv
    from sqlalchemy.orm import selectinload

    q = select(Message).options(selectinload(Message.reactions), selectinload(Message.author), selectinload(Message.attachments)).where(
        Message.direct_conversation_id == conv_id,
        Message.is_deleted == False,
        Message.parent_id.is_(None)
    )
    if join_ts:
        # Allow slight timestamp jitter (server-default timestamps may be second-precision)
        from datetime import timedelta
        q = q.where(Message.created_at >= (join_ts - timedelta(seconds=1)))
    q = q.order_by(Message.last_activity_at.desc(), Message.created_at.desc()).offset(skip).limit(limit)
    r = await db.execute(q)
    msgs = r.scalars().all()

    # Reply counts
    message_ids = [m.id for m in msgs]
    reply_counts = {}
    if message_ids:
        rc_q = select(Message.parent_id, func.count(Message.id)).where(Message.parent_id.in_(message_ids), Message.is_deleted == False).group_by(Message.parent_id)
        rr = await db.execute(rc_q)
        reply_counts = dict(rr.all())

    res = [transform_message_to_response(m, reply_count=reply_counts.get(m.id, 0)) for m in reversed(msgs)]
    return res


@router.post("/{conv_id}/messages", status_code=status.HTTP_201_CREATED)
async def post_direct_conversation_message(
    conv_id: int,
    request: DirectMessageCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a message in a direct conversation. Also emits thread:reply for replies."""
    # Check membership
    r = await db.execute(select(DirectConversationParticipant).where(DirectConversationParticipant.direct_conversation_id == conv_id, DirectConversationParticipant.user_id == current_user["user_id"]))
    member = r.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=403, detail="You are not a participant in this direct conversation.")

    # Check content
    content = request.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Content cannot be empty")

    # Check user can post (ban/mute)
    can_post = await check_user_can_post(db, current_user["user_id"]) 
    if not can_post:
        raise HTTPException(status_code=403, detail="You are not allowed to post messages (banned or muted)")

    # If parent_id provided, verify it exists and belongs to this conv
    parent_msg = None
    if request.parent_id:
        pr = await db.execute(select(Message).where(Message.id == request.parent_id, Message.direct_conversation_id == conv_id))
        parent_msg = pr.scalar_one_or_none()
        if not parent_msg:
            raise HTTPException(status_code=404, detail="Parent message not found")

    # Create message
    msg = Message(content=content, direct_conversation_id=conv_id, author_id=current_user["user_id"], parent_id=request.parent_id)
    db.add(msg)
    if parent_msg:
        parent_msg.thread_count = (parent_msg.thread_count or 0) + 1
        parent_msg.last_activity_at = func.now()
    await db.commit()
    await db.refresh(msg)

    # Re-fetch with relationships loaded to avoid async lazy loads
    from sqlalchemy.orm import selectinload
    r = await db.execute(select(Message).options(selectinload(Message.reactions), selectinload(Message.author), selectinload(Message.attachments)).where(Message.id == msg.id))
    msg = r.scalar_one()

    # NOTE: thread:reply emit handled below after emitting message new

    # Broadcast to WebSocket (non-Socket.IO) if there are websocket subscribers for room dm:{id}
    try:
        room_key = f"dm:{conv_id}"
        conns = manager.channel_connections.get(room_key, set())
        for ws, uid in list(conns):
            if uid == current_user["user_id"]:
                continue
            try:
                await ws.send_json({
                    "type": "message",
                    "id": msg.id,
                    "content": msg.content,
                    "user_id": current_user["user_id"],
                    "username": None,
                    "direct_conversation_id": conv_id,
                    "timestamp": msg.created_at.isoformat(),
                })
            except Exception:
                pass
    except Exception:
        pass

    # Create a persistent notification for the other participant about the new DM message (Phase N2)
    try:
        from app.db.enums import NotificationType
        from app.services.notification_emitter import create_and_emit_notification

        # Determine other participant (only notify the other user, not the sender)
        pr = await db.execute(select(DirectConversationParticipant).where(DirectConversationParticipant.direct_conversation_id == conv_id))
        participants = pr.scalars().all()
        other_participant = next((p for p in participants if p.user_id != current_user["user_id"]), None)
        if other_participant:
            sender_username = current_user.get('username') or f"user_{current_user['user_id']}"
            await create_and_emit_notification(
                db,
                user_id=other_participant.user_id,
                notification_type=NotificationType.dm_message,
                title=f"New message from {sender_username}",
                content=(msg.content or '')[:100],
                message_id=msg.id,
                sender_id=current_user['user_id'],
                metadata={"direct_conversation_id": conv_id},
            )
    except Exception:
        # Non-fatal - notification creation should not fail the message post
        logger.exception('Failed to create DM notification')

    # Log message timestamps for debugging join timestamp exclusion issues
    # created message logged by audit/logging elsewhere if needed

    # Emit Socket.IO event to room dm:{conv_id}
    try:
        from app.realtime.socket import emit_message_new, emit_thread_reply_dm
        payload = {
            "id": msg.id,
            "content": msg.content,
            "direct_conversation_id": conv_id,
            "author_id": current_user["user_id"],
            "parent_id": request.parent_id,
            "created_at": msg.created_at.isoformat(),
        }
        await emit_message_new(0, payload, room_name=f"dm:{conv_id}")

        # If this message is a reply to a parent in a DM, also emit thread:reply for DM rooms
        if parent_msg:
            username = msg.author.username if msg.author else f"user_{current_user['user_id']}"
            reply_payload = {
                "id": msg.id,
                "content": msg.content,
                "direct_conversation_id": conv_id,
                "author_id": current_user["user_id"],
                "author_username": username,
                "parent_id": request.parent_id,
                "created_at": msg.created_at.isoformat(),
                "is_edited": False,
                "reactions": [],
            }
            await emit_thread_reply_dm(conv_id, request.parent_id, reply_payload)

            # Create a notification for the parent message author (dm_reply)
            try:
                from app.db.enums import NotificationType
                from app.services.notification_emitter import create_and_emit_notification
                # Ensure parent author exists, parent not deleted, and is not the replier
                if parent_msg and not getattr(parent_msg, 'is_deleted', False) and parent_msg.author_id and parent_msg.author_id != current_user['user_id']:
                    # Check author is still active
                    from app.db.models import User as UserModel
                    r = await db.execute(select(UserModel).where(UserModel.id == parent_msg.author_id, UserModel.is_active == True))
                    parent_author = r.scalar_one_or_none()
                    if parent_author:
                        sender_username = current_user.get('username') or f"user_{current_user['user_id']}"
                        await create_and_emit_notification(
                            db,
                            user_id=parent_author.id,
                            notification_type=NotificationType.dm_reply,
                            title=f"New reply from {sender_username}",
                            content=(msg.content or '')[:100],
                            message_id=msg.id,
                            sender_id=current_user['user_id'],
                            metadata={"direct_conversation_id": conv_id, "parent_id": request.parent_id},
                        )
            except Exception:
                logger.exception('Failed to create DM reply notification')
    except Exception:
        pass

    return transform_message_to_response(msg)


class DirectConversationReadResponse(BaseModel):
    user_id: int
    last_read_message_id: Optional[int]

    class Config:
        from_attributes = True


class MarkReadRequest(BaseModel):
    last_read_message_id: int


@router.get("/{conv_id}/reads", response_model=List[DirectConversationReadResponse])
async def get_direct_conversation_reads(
    conv_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all read receipts for a direct conversation.
    Returns list of {user_id, last_read_message_id} for computing "Seen by X".
    """
    # Verify user is participant
    r = await db.execute(
        select(DirectConversationParticipant).where(
            DirectConversationParticipant.direct_conversation_id == conv_id,
            DirectConversationParticipant.user_id == current_user["user_id"]
        )
    )
    if not r.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="You are not a participant in this direct conversation.")

    # Get all read receipts for this conversation
    reads_query = select(DirectConversationRead).where(DirectConversationRead.direct_conversation_id == conv_id)
    reads_result = await db.execute(reads_query)
    reads = reads_result.scalars().all()

    return [
        {"user_id": r.user_id, "last_read_message_id": r.last_read_message_id}
        for r in reads
    ]


@router.post("/{conv_id}/reads", response_model=DirectConversationReadResponse)
async def mark_direct_conversation_read(
    conv_id: int,
    request: MarkReadRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Mark a direct conversation as read up to a specific message.
    Upserts the read record and emits direct:read_updated to the dm room.
    """
    user_id = current_user["user_id"]

    # Verify user is participant
    r = await db.execute(
        select(DirectConversationParticipant).where(
            DirectConversationParticipant.direct_conversation_id == conv_id,
            DirectConversationParticipant.user_id == user_id
        )
    )
    if not r.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="You are not a participant in this direct conversation.")

    # Verify message exists and belongs to this conversation
    msg_result = await db.execute(
        select(Message).where(
            Message.id == request.last_read_message_id,
            Message.direct_conversation_id == conv_id,
            Message.is_deleted == False
        )
    )
    if not msg_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Message not found in this conversation")

    # Upsert read record
    read_result = await db.execute(
        select(DirectConversationRead).where(
            DirectConversationRead.direct_conversation_id == conv_id,
            DirectConversationRead.user_id == user_id
        )
    )
    read_record = read_result.scalar_one_or_none()

    should_emit = False
    if read_record:
        # Only update if new message_id is higher (or if current is None)
        if read_record.last_read_message_id is None or request.last_read_message_id > read_record.last_read_message_id:
            read_record.last_read_message_id = request.last_read_message_id
            should_emit = True
    else:
        read_record = DirectConversationRead(
            user_id=user_id,
            direct_conversation_id=conv_id,
            last_read_message_id=request.last_read_message_id
        )
        db.add(read_record)
        should_emit = True

    await db.commit()
    await db.refresh(read_record)

    # Emit socket event to dm:{conv_id} room
    if should_emit:
        try:
            await emit_direct_read_updated(conv_id, user_id, read_record.last_read_message_id)
        except Exception as e:
            logger.warning(f"Socket.IO emit failed for direct read update: {e}")

    return {"user_id": user_id, "last_read_message_id": read_record.last_read_message_id}
