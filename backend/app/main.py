from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import select

from app.api import auth, users, teams, channels, messages, websocket, ws, notifications, admin
from app.db.database import create_tables, async_session
from app.db.models import Team, Channel, ChannelType, User, UserRole
from app.core.config import settings
from app.core.security import get_password_hash


async def seed_default_data():
    """Seed default team, channels, and admin user if they don't exist"""
    async with async_session() as db:
        # Check if admin user exists using raw SQL to avoid enum value coercion issues
        from sqlalchemy import text
        result = await db.execute(text("SELECT id, email FROM users WHERE email = :email"), {"email": "admin@fearallah.com"})
        row = result.first()
        admin = None
        if row:
            # row is a lightweight RowProxy; we don't need full ORM mapping here
            admin = row
        
        if not admin:
            # Create admin user
            admin = User(
                username='admin',
                email='admin@fearallah.com',
                hashed_password=get_password_hash('admin123'),
                display_name='Admin',
                role=UserRole.system_admin.value,
                is_system_admin=True,
                is_active=True
            )
            db.add(admin)
            await db.commit()
            await db.refresh(admin)
            from app.core.config import logger
            logger.info("Created admin user: admin@fearallah.com / admin123")
        else:
            from app.core.config import logger
            logger.info(f"Admin user already exists: {admin.email}")
        
        # Check if default team exists
        result = await db.execute(select(Team).where(Team.name == 'default'))
        team = result.scalar_one_or_none()
        
        if not team:
            # Create default team
            team = Team(
                name='default',
                display_name='Default Team',
                description='The default workspace team'
            )
            db.add(team)
            await db.commit()
            await db.refresh(team)
            
            # Create default channels
            default_channels = [
                Channel(name='general', display_name='General', description='General discussion', type=ChannelType.public.value, team_id=team.id),
                Channel(name='random', display_name='Random', description='Random chat', type=ChannelType.public.value, team_id=team.id),
                Channel(name='dev', display_name='Development', description='Development discussions', type=ChannelType.public.value, team_id=team.id),
            ]
            for channel in default_channels:
                db.add(channel)
            await db.commit()
            from app.core.config import logger
            logger.info(f"Created default team '{team.name}' with {len(default_channels)} channels")
        else:
            from app.core.config import logger
            logger.info(f"Default team already exists: {team.name}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await create_tables()
    await seed_default_data()
    # Start Redis pub/sub listener for cross-pod broadcasts (Phase 9)
    try:
        from app.core.redis import redis_client
        from app.ws.redis_pubsub import start_redis_listener
        from app.api.ws import manager as ws_manager
        app.state._redis_listener = start_redis_listener(redis_client, ws_manager)
    except Exception:
        # Best-effort: do not fail startup if redis listener cannot be started
        app.state._redis_listener = None
    yield
    # Shutdown
    # Stop Redis pub/sub listener if running
    ctl = getattr(app.state, '_redis_listener', None)
    if ctl and ctl.get('stop_event'):
        try:
            ctl['stop_event'].set()
            th = ctl.get('thread')
            if th and th.is_alive():
                th.join(timeout=2)
        except Exception:
            pass


app = FastAPI(
    title="fear-Allah API",
    description="Backend API for fear-Allah chat application",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
# Configure CORS to match Mattermost-style behavior for uploads and API access
# Allow GET/HEAD as well so preflights for authenticated GET requests succeed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(teams.router, prefix="/api/teams", tags=["Teams"])
app.include_router(channels.router, prefix="/api/channels", tags=["Channels"])
app.include_router(messages.router, prefix="/api/messages", tags=["Messages"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["Notifications"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(websocket.router, prefix="/api/ws", tags=["WebSocket Legacy"])
app.include_router(ws.router, prefix="/ws", tags=["WebSocket"])

# Health / readiness endpoints (Tier 2.3)
from app.api import health
app.include_router(health.router, prefix="", tags=["Health"])

# Orders & Tasks
from app.api import orders, tasks
app.include_router(orders.router, prefix="/api/orders", tags=["Orders"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["Tasks"])

# Sales (event-based, not workflows)
from app.api import sales
app.include_router(sales.router, prefix="/api/sales", tags=["Sales"])
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "fear-Allah API"}


@app.get("/api/health")
async def api_health_check():
    return {"status": "ok", "service": "fear-Allah API"}
