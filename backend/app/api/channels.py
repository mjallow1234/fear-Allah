from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from pydantic import BaseModel
from typing import Optional, List, Literal
from datetime import datetime
import uuid

from app.db.database import get_db
from app.db.models import Channel, ChannelMember, ChannelType, Team, FileAttachment, AuditLog, User
from app.core.security import get_current_user
from app.storage.minio_client import get_minio_storage

router = APIRouter()


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

    class Config:
        from_attributes = True


@router.post("/", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
async def create_channel(
    request: ChannelCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # If team_id provided, verify team exists
    if request.team_id:
        query = select(Team).where(Team.id == request.team_id)
        result = await db.execute(query)
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Team not found")
    
    channel = Channel(
        name=request.name,
        display_name=request.display_name or request.name,
        description=request.description,
        type=(ChannelType(request.type).value if request.type else ChannelType.public.value),
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
    
    return channel


@router.get("/", response_model=List[ChannelResponse])
async def list_channels(
    team_id: Optional[int] = None,
    include_dms: bool = False,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if team_id:
        query = select(Channel).where(Channel.team_id == team_id, Channel.type != ChannelType.direct)
    elif include_dms:
        # Get DM channels where user is a member
        dm_query = (
            select(Channel)
            .join(ChannelMember, Channel.id == ChannelMember.channel_id)
            .where(
                ChannelMember.user_id == current_user["user_id"],
                Channel.type == ChannelType.direct
            )
        )
        result = await db.execute(dm_query)
        return result.scalars().all()
    else:
        query = select(Channel).where(Channel.team_id.is_(None), Channel.type != ChannelType.direct)
    
    result = await db.execute(query)
    channels = result.scalars().all()
    return channels


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
    
    # Get all DM channels where user is a member
    dm_query = (
        select(Channel)
        .join(ChannelMember, Channel.id == ChannelMember.channel_id)
        .where(
            ChannelMember.user_id == my_user_id,
            Channel.type == ChannelType.direct
        )
    )
    result = await db.execute(dm_query)
    dm_channels = result.scalars().all()
    
    # For each channel, find the other user
    dm_list = []
    for channel in dm_channels:
        # Get the other member
        other_member_query = (
            select(ChannelMember)
            .options()
            .where(
                ChannelMember.channel_id == channel.id,
                ChannelMember.user_id != my_user_id
            )
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
        raise HTTPException(status_code=400, detail="Not a member of this channel")
    
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
    
    # Read file content
    content = await file.read()
    file_size = len(content)
    
    # Generate unique filename
    ext = file.filename.split(".")[-1] if "." in file.filename else ""
    unique_filename = f"{channel_id}/{uuid.uuid4()}.{ext}" if ext else f"{channel_id}/{uuid.uuid4()}"
    
    # Upload to MinIO
    try:
        storage = get_minio_storage()
        file_path = await storage.upload_file(
            content,
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


@router.post("/{channel_id}/members", response_model=ChannelMemberResponse)
async def add_channel_member(
    channel_id: int,
    request: AddMemberRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Add a user to a channel."""
    # Verify channel exists and is not a DM
    channel_query = select(Channel).where(Channel.id == channel_id)
    channel_result = await db.execute(channel_query)
    channel = channel_result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    if str(channel.type) == ChannelType.direct.value:
        raise HTTPException(status_code=400, detail="Cannot add members to DM channels")
    
    # For private channels, check if current user is a member
    if str(channel.type) == ChannelType.private.value:
        member_query = select(ChannelMember).where(
            ChannelMember.channel_id == channel_id,
            ChannelMember.user_id == current_user["user_id"]
        )
        member_result = await db.execute(member_query)
        if not member_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Only members can add users to private channels")
    
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


@router.delete("/{channel_id}/members/{user_id}")
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
    
    if str(channel.type) == ChannelType.direct.value:
        raise HTTPException(status_code=400, detail="Cannot remove members from DM channels")
    
    # Check if current user has permission (system admin or removing themselves)
    current_user_query = select(User).where(User.id == current_user["user_id"])
    current_user_result = await db.execute(current_user_query)
    curr_user = current_user_result.scalar_one_or_none()
    
    if not curr_user.is_system_admin and user_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Only admins can remove other users")
    
    # Find and remove membership
    member_query = select(ChannelMember).where(
        ChannelMember.channel_id == channel_id,
        ChannelMember.user_id == user_id
    )
    member_result = await db.execute(member_query)
    membership = member_result.scalar_one_or_none()
    
    if not membership:
        raise HTTPException(status_code=404, detail="User is not a member of this channel")
    
    await db.delete(membership)
    await db.commit()
    
    return {"message": "User removed from channel"}
