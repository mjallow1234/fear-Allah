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
    """Initialize the system.

    - Runs in a single DB transaction
    - Idempotent: if setup_completed is true -> 409
    - Prevents creating resources if users or teams already exist
    - Uses an insert-if-not-exists + SELECT FOR UPDATE to serialize concurrent initializers
    """
    from sqlalchemy import text, update
    from sqlalchemy.exc import IntegrityError
    from app.db.models import SystemState, TeamMember, ChannelMember

    # Run everything inside a transaction to ensure atomicity
    async with db.begin():
        # Ensure a singleton SystemState row exists (id=1); use ON CONFLICT DO NOTHING to avoid races
        await db.execute(
            text("INSERT INTO system_state (id, setup_completed) VALUES (1, false) ON CONFLICT (id) DO NOTHING")
        )

        # Lock the state row for update to serialize concurrent initializations
        result = await db.execute(select(SystemState).where(SystemState.id == 1).with_for_update())
        state = result.scalar_one_or_none()

        if state and state.setup_completed:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="System already initialized")

        # Prevent initialization if any users or teams already exist (to avoid duplicates)
        users_count = await db.scalar(select(func.count(User.id))) or 0
        teams_count = await db.scalar(select(func.count(Team.id))) or 0
        if users_count > 0 or teams_count > 0:
            # Do not allow creating second admin/team; require manual intervention or migration
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="System already has users or teams; cannot initialize")

        # Create admin user
        admin = User(
            username=request.admin_name.replace("@", "-at-"),
            email=request.admin_email,
            display_name=request.admin_name,
            hashed_password=get_password_hash(request.admin_password),
            is_active=True,
            is_system_admin=True,
            operational_role='agent',  # sensible default for initial admin
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
        membership = TeamMember(user_id=admin.id, team_id=team.id, role="admin")
        db.add(membership)
        cm = ChannelMember(user_id=admin.id, channel_id=channel.id)
        db.add(cm)

        # Persist the setup flag (set true)
        if not state:
            new_state = SystemState(id=1, setup_completed=True)
            db.add(new_state)
        else:
            await db.execute(
                update(SystemState).where(SystemState.id == 1).values(setup_completed=True)
            )

    # Transaction committed successfully here

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
