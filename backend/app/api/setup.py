from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.db.models import User, Team, Channel
from app.core.security import get_password_hash

router = APIRouter()


class SetupRequest(BaseModel):
    admin_name: str
    admin_email: EmailStr
    admin_password: str
    team_name: str


class SetupResponse(BaseModel):
    user: dict
    team: dict


@router.post("/initialize", response_model=SetupResponse)
async def initialize_system(request: SetupRequest, db: AsyncSession = Depends(get_db)):
    # Check if system already initialized
    users_count = await db.scalar(select(func.count(User.id))) or 0
    teams_count = await db.scalar(select(func.count(Team.id))) or 0

    if users_count > 0 and teams_count > 0:
        # System already initialized; return 409 (idempotent-safe)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="System already initialized")

    # Create admin user
    admin = User(
        username=request.admin_name.replace("@", "-at-"),
        email=request.admin_email,
        display_name=request.admin_name,
        hashed_password=get_password_hash(request.admin_password),
        is_active=True,
        is_system_admin=True,
    )
    db.add(admin)
    await db.flush()
    await db.refresh(admin)

    # Create team
    team = Team(name=request.team_name.lower().replace(" ", "-"), display_name=request.team_name)
    db.add(team)
    await db.flush()
    await db.refresh(team)

    # Create default channel
    channel = Channel(name="town-square", display_name="Town Square", description="General", team_id=team.id)
    db.add(channel)
    await db.flush()
    await db.refresh(channel)

    # Add membership for admin
    from app.db.models import TeamMember, ChannelMember

    membership = TeamMember(user_id=admin.id, team_id=team.id, role="admin")
    db.add(membership)
    cm = ChannelMember(user_id=admin.id, channel_id=channel.id)
    db.add(cm)

    await db.commit()

    return {
        "user": {
            "id": admin.id,
            "username": admin.username,
            "email": admin.email,
            "display_name": admin.display_name,
            "is_system_admin": admin.is_system_admin,
        },
        "team": {
            "id": team.id,
            "name": team.name,
            "display_name": team.display_name,
        }
    }
