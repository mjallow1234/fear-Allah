from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, and_, or_
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.db.database import get_db
from app.db.models import Notification, NotificationType, User, Channel, Message
from app.core.security import get_current_user

router = APIRouter()


class NotificationResponse(BaseModel):
    id: int
    type: str
    title: str
    content: Optional[str]
    channel_id: Optional[int]
    message_id: Optional[int]
    sender_id: Optional[int]
    sender_username: Optional[str] = None
    # Automation context (Phase 6.4)
    task_id: Optional[int] = None
    order_id: Optional[int] = None
    inventory_id: Optional[int] = None
    sale_id: Optional[int] = None
    extra_data: Optional[str] = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationCountResponse(BaseModel):
    unread: int
    total: int


@router.get("/", response_model=List[NotificationResponse])
async def list_notifications(
    limit: int = 50,
    unread_only: bool = False,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get notifications for the current user"""
    query = select(Notification).where(Notification.user_id == current_user["user_id"])
    
    if unread_only:
        query = query.where(Notification.is_read == False)
    
    query = query.order_by(Notification.created_at.desc()).limit(limit)
    query = query.options(selectinload(Notification.sender))
    
    result = await db.execute(query)
    notifications = result.scalars().all()
    
    response = []
    for n in notifications:
        n_type = n.type.value if hasattr(n.type, 'value') else n.type
        response.append(NotificationResponse(
            id=n.id,
            type=n_type,
            title=n.title,
            content=n.content,
            channel_id=n.channel_id,
            message_id=n.message_id,
            sender_id=n.sender_id,
            sender_username=n.sender.username if n.sender else None,
            task_id=n.task_id,
            order_id=n.order_id,
            inventory_id=n.inventory_id,
            sale_id=n.sale_id,
            extra_data=n.extra_data,
            is_read=n.is_read,
            created_at=n.created_at
        ))
    
    return response


@router.get("/count", response_model=NotificationCountResponse)
async def get_notification_count(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get unread and total notification count"""
    # Get unread count
    unread_query = select(func.count(Notification.id)).where(
        and_(
            Notification.user_id == current_user["user_id"],
            Notification.is_read == False
        )
    )
    unread_result = await db.execute(unread_query)
    unread_count = unread_result.scalar() or 0
    
    # Get total count
    total_query = select(func.count(Notification.id)).where(
        Notification.user_id == current_user["user_id"]
    )
    total_result = await db.execute(total_query)
    total_count = total_result.scalar() or 0
    
    return NotificationCountResponse(unread=unread_count, total=total_count)


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark a notification as read"""
    query = select(Notification).where(
        and_(
            Notification.id == notification_id,
            Notification.user_id == current_user["user_id"]
        )
    )
    result = await db.execute(query)
    notification = result.scalar_one_or_none()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    notification.is_read = True
    await db.commit()
    
    return {"success": True}


@router.post("/read-all")
async def mark_all_notifications_read(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark all notifications as read"""
    stmt = update(Notification).where(
        and_(
            Notification.user_id == current_user["user_id"],
            Notification.is_read == False
        )
    ).values(is_read=True)
    
    await db.execute(stmt)
    await db.commit()
    
    return {"success": True}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a notification"""
    query = select(Notification).where(
        and_(
            Notification.id == notification_id,
            Notification.user_id == current_user["user_id"]
        )
    )
    result = await db.execute(query)
    notification = result.scalar_one_or_none()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    await db.delete(notification)
    await db.commit()
    
    return {"success": True}


class MarkFilteredRequest(BaseModel):
    direct_conversation_id: Optional[int] = None
    channel_id: Optional[int] = None
    parent_id: Optional[int] = None
    types: Optional[List[str]] = None


@router.post("/read-filtered")
async def mark_notifications_read_filtered(
    request: MarkFilteredRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark notifications as read filtered by conversation/channel/parent or types

    This endpoint supports marking a subset of notifications as read, e.g. when a user opens
    a DM or channel or views a thread.
    """
    conditions = [Notification.user_id == current_user["user_id"], Notification.is_read == False]

    # Apply filters
    if request.channel_id is not None:
        conditions.append(Notification.channel_id == request.channel_id)

    if request.direct_conversation_id is not None:
        # extra_data stores JSON; use a simple text match to find the direct_conversation_id
        conditions.append(Notification.extra_data.ilike(f'%"direct_conversation_id": {request.direct_conversation_id}%'))

    if request.parent_id is not None:
        conditions.append(
            or_(
                Notification.extra_data.ilike(f'%"parent_id": {request.parent_id}%'),
                Notification.message_id == request.parent_id
            )
        )

    if request.types:
        conditions.append(Notification.type.in_(request.types))

    stmt = update(Notification).where(*conditions).values(is_read=True)
    result = await db.execute(stmt)
    await db.commit()

    # Emit updated unread count for the user
    unread_query = select(func.count(Notification.id)).where(Notification.user_id == current_user["user_id"], Notification.is_read == False)
    unread_res = await db.execute(unread_query)
    unread_count = unread_res.scalar() or 0

    try:
        from app.services.notification_emitter import emit_notification_count_update
        await emit_notification_count_update(current_user["user_id"], unread_count)
    except Exception:
        # Non-fatal
        pass

    return {"updated": result.rowcount}

# Helper function to create notifications (used by other modules)
async def create_notification(
    db: AsyncSession,
    user_id: int,
    notification_type: NotificationType,
    title: str,
    content: Optional[str] = None,
    channel_id: Optional[int] = None,
    message_id: Optional[int] = None,
    sender_id: Optional[int] = None
):
    """Create a new notification"""
    notif_type_val = notification_type.value if hasattr(notification_type, 'value') else notification_type
    notification = Notification(
        user_id=user_id,
        type=notif_type_val,
        title=title,
        content=content,
        channel_id=channel_id,
        message_id=message_id,
        sender_id=sender_id
    )
    db.add(notification)
    await db.commit()
    await db.refresh(notification)
    return notification
