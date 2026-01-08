from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from typing import List

from app.db.database import get_db
from app.db.models import Team, TeamMember, Channel, ChannelMember, User
from app.core.security import get_current_user
from app.api.ws import manager as ws_manager

router = APIRouter()


class FirstTeamCreateRequest(BaseModel):
    name: str
    display_name: str | None = None
    description: str | None = None


class FirstTeamResponse(BaseModel):
    id: int
    name: str
    display_name: str | None = None
    channels: List[dict]

    class Config:
        from_attributes = True


@router.post("/first-team", response_model=FirstTeamResponse, status_code=status.HTTP_201_CREATED)
async def create_first_team(
    request: FirstTeamCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Allow creating first team only when no teams exist
    total_q = await db.execute(select(func.count(Team.id)))
    total = total_q.scalar_one()
    if total and total > 0:
        raise HTTPException(status_code=403, detail="First-team onboarding not allowed: teams already exist")

    # Create team
    team = Team(name=request.name, display_name=request.display_name or request.name, description=request.description)
    db.add(team)
    await db.commit()
    await db.refresh(team)

    # Promote user to system admin (first user becomes system admin)
    user_q = await db.execute(select(User).where(User.id == current_user["user_id"]))
    user = user_q.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Current user not found")

    user.is_system_admin = True
    await db.commit()

    # Add creator as team admin
    membership = TeamMember(user_id=user.id, team_id=team.id, role="admin")
    db.add(membership)
    await db.commit()

    # Create default channels for the new team and add creator as member
    default_channels = [
        {"name": "town-square", "display_name": "Town Square", "description": "General discussion"},
        {"name": "off-topic", "display_name": "Off-topic", "description": "Off-topic discussion"},
    ]

    created_channels = []
    for ch in default_channels:
        channel = Channel(name=ch["name"], display_name=ch["display_name"], description=ch["description"], team_id=team.id)
        db.add(channel)
        await db.flush()
        # add creator as member
        cm = ChannelMember(user_id=user.id, channel_id=channel.id)
        db.add(cm)
        await db.commit()
        await db.refresh(channel)

        # Broadcast channel_created via presence so sidebar updates instantly
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
            # Best-effort: do not fail onboarding if broadcast fails
            import logging
            logging.exception("Failed to broadcast channel_created during onboarding")

        created_channels.append({
            "id": channel.id,
            "name": channel.name,
            "display_name": channel.display_name,
            "description": channel.description,
            "team_id": channel.team_id,
        })

    return FirstTeamResponse(id=team.id, name=team.name, display_name=team.display_name, channels=created_channels)
