from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List

from app.db.database import get_db
from app.db.models import Team, TeamMember, User
from app.core.security import get_current_user

router = APIRouter()


class TeamCreateRequest(BaseModel):
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None


class TeamResponse(BaseModel):
    id: int
    name: str
    display_name: Optional[str]
    description: Optional[str]
    icon_url: Optional[str]

    class Config:
        from_attributes = True


class TeamMemberResponse(BaseModel):
    id: int
    user_id: int
    team_id: int
    role: str
    username: Optional[str] = None
    display_name: Optional[str] = None

    class Config:
        from_attributes = True


@router.post("/", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    request: TeamCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Check if user is system admin
    query = select(User).where(User.id == current_user["user_id"])
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user or not user.is_system_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only system admins can create teams"
        )
    
    # Check if team name exists
    query = select(Team).where(Team.name == request.name)
    result = await db.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team name already exists"
        )
    
    team = Team(
        name=request.name,
        display_name=request.display_name or request.name,
        description=request.description,
    )
    db.add(team)
    await db.commit()
    await db.refresh(team)
    
    # Add creator as admin
    membership = TeamMember(
        user_id=current_user["user_id"],
        team_id=team.id,
        role="admin"
    )
    db.add(membership)
    await db.commit()
    
    return team


@router.get("", response_model=List[TeamResponse])
@router.get("/", response_model=List[TeamResponse])
async def list_teams(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Team)
    result = await db.execute(query)
    teams = result.scalars().all()
    return teams


@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(
    team_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Team).where(Team.id == team_id)
    result = await db.execute(query)
    team = result.scalar_one_or_none()
    
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    return team


@router.post("/{team_id}/members", response_model=TeamMemberResponse)
async def add_team_member(
    team_id: int,
    user_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Check team exists
    query = select(Team).where(Team.id == team_id)
    result = await db.execute(query)
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    # Check if already a member
    query = select(TeamMember).where(
        TeamMember.team_id == team_id,
        TeamMember.user_id == user_id
    )
    result = await db.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User is already a team member")
    
    membership = TeamMember(user_id=user_id, team_id=team_id, role="member")
    db.add(membership)
    await db.commit()
    await db.refresh(membership)
    
    return membership


@router.get("/{team_id}/members", response_model=List[TeamMemberResponse])
async def list_team_members(
    team_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from sqlalchemy.orm import selectinload
    query = select(TeamMember).options(selectinload(TeamMember.user)).where(TeamMember.team_id == team_id)
    result = await db.execute(query)
    members = result.scalars().all()
    
    # Return members with user info
    return [
        {
            "id": m.id,
            "user_id": m.user_id,
            "team_id": m.team_id,
            "role": m.role,
            "username": m.user.username if m.user else None,
            "display_name": m.user.display_name if m.user else None,
        }
        for m in members
    ]
