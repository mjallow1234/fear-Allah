from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from contextlib import asynccontextmanager
from sqlalchemy import select

from app.api import auth, users, teams, channels, messages, websocket, ws, notifications, admin, system, attachments, audit, audit, direct_conversations
from app.db.database import create_tables, async_session
from app.db.models import Team, Channel, ChannelType, User, UserRole
from app.core.config import settings
from app.core.security import get_password_hash
from app.core.middleware import (
    RequestContextMiddleware,
    RateLimitMiddleware,
    global_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.core.logging import api_logger
from app.core.rate_limit_config import rate_limit_settings
# Ensure AuditLog model is imported so Alembic/SQLAlchemy sees it
from app.db.models import AuditLog  # noqa: F401

# Socket.IO for real-time (Phase 4.1)
from app.realtime import socket_app


async def seed_default_data():
    """Seed default team, channels, and admin user if they don't exist"""
    async with async_session() as db:
        # Check if admin user exists by email OR username (avoid collision)
        from sqlalchemy import text
        result = await db.execute(
            text("SELECT id, email FROM users WHERE email = :email OR username = :username"),
            {"email": "admin@fearallah.com", "username": "admin"}
        )
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
    # When running tests we intentionally skip creating tables and seeding demo data to avoid
    # connecting to external databases during app startup. Tests use their own test engine/fixtures
    # (see backend/tests/conftest.py) and seed DB state explicitly where needed.
    if not settings.TESTING:
        await create_tables()
        await seed_default_data()
        # Seed demo RBAC channel roles (dev-only)
        from app.permissions.demo_seeder import run_demo_seeder
        await run_demo_seeder()

        # Run assignment backfill to resolve legacy placeholder assignments (foreman/delivery)
        # NOTE: Backfill is potentially destructive for current data - only run when explicitly
        # enabled via BACKFILL_ON_STARTUP. By default this is disabled and should be run
        # manually via scripts for historical data only.
        try:
            from app.core.config import settings as _settings
            if getattr(_settings, 'BACKFILL_ON_STARTUP', False):
                from app.automation.backfill import backfill_assignments
                async with async_session() as db:
                    updated = await backfill_assignments(db)
                    from app.core.config import logger
                    logger.info(f"[Backfill] Resolved {updated} placeholder assignment(s)")
            else:
                from app.core.config import logger
                logger.info("[Backfill] Skipped at startup (BACKFILL_ON_STARTUP is false)")
        except Exception as e:
            from app.core.config import logger
            logger.warning(f"[Backfill] Failed to backfill assignments at startup: {e}")

    # Start Redis pub/sub listener for cross-pod broadcasts (Phase 9)
    # Do NOT start Redis listener during tests to avoid background threads and external network calls.
    if not settings.TESTING:
        try:
            from app.core.redis import redis_client
            from app.ws.redis_pubsub import start_redis_listener
            from app.api.ws import manager as ws_manager
            app.state._redis_listener = start_redis_listener(redis_client, ws_manager)
        except Exception:
            # Best-effort: do not fail startup if redis listener cannot be started
            app.state._redis_listener = None
    else:
        app.state._redis_listener = None
    
    # Start AI scheduler if enabled (Phase 4.2)
    # Default: disabled. Set AI_SCHEDULER_ENABLED=true in environment to enable.
    import os
    ai_scheduler_enabled = os.getenv("AI_SCHEDULER_ENABLED", "false").lower() == "true"
    if ai_scheduler_enabled and not settings.TESTING:
        try:
            from app.ai.scheduler import setup_scheduler
            setup_scheduler()
            from app.core.config import logger
            logger.info("[AI Scheduler] Started automatically (AI_SCHEDULER_ENABLED=true)")
        except Exception as e:
            from app.core.config import logger
            logger.warning(f"[AI Scheduler] Failed to start: {e}")
    else:
        from app.core.config import logger
        logger.info("[AI Scheduler] Disabled (set AI_SCHEDULER_ENABLED=true to enable)")
    
    yield
    # Shutdown
    # Stop AI scheduler if running
    try:
        from app.ai.scheduler import shutdown_scheduler
        shutdown_scheduler()
    except Exception:
        pass
    
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

# === MIDDLEWARE SETUP ===
# NOTE: Starlette middleware runs in REVERSE order (LIFO - last added runs first)
# So we add them in reverse order of desired execution:
# 1. RateLimitMiddleware (last to run, after auth)
# 2. RequestContextMiddleware (request_id, timing)
# 3. CORSMiddleware (FIRST to run - must handle OPTIONS before anything else)

# Rate limiting middleware (Phase 8.3 - abuse protection)
# Runs LAST - after auth checks in route handlers
# Do not enable rate limiting when running tests (TESTING=true)
if rate_limit_settings.ENABLED and not settings.TESTING:
    app.add_middleware(RateLimitMiddleware)
    api_logger.info("Rate limiting enabled")
else:
    api_logger.info("Rate limiting disabled (testing or env disabled)")

# Request context middleware (Phase 8.1 - request_id, timing, logging)
# Runs SECOND - sets up request context
app.add_middleware(RequestContextMiddleware)

# CORS middleware - MUST run FIRST to handle OPTIONS preflight
# Added LAST so it runs FIRST (LIFO order)
# Phase 8.4.3 - Explicit headers for preflight
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app.sidrahsalaam.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers (Phase 8.1 - safe JSON responses)
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

api_logger.info("Application initialized", env=settings.APP_ENV)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(teams.router, prefix="/api/teams", tags=["Teams"])
app.include_router(channels.router, prefix="/api/channels", tags=["Channels"])
app.include_router(messages.router, prefix="/api/messages", tags=["Messages"])
app.include_router(direct_conversations.router, prefix="/api/direct-conversations", tags=["DirectConversations"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["Notifications"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(system.router, prefix="/api/system", tags=["System Console"])
app.include_router(attachments.router, prefix="/api/attachments", tags=["File Attachments"])
app.include_router(websocket.router, prefix="/api/ws", tags=["WebSocket Legacy"])
app.include_router(ws.router, prefix="/ws", tags=["WebSocket"])

# Audit: Read-only audit log viewer (Phase 4.1)
app.include_router(audit.router, prefix="/api/audit", tags=["Audit"])
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

# Inventory (Phase 6.3)
from app.api import inventory
app.include_router(inventory.router, prefix="/api/inventory", tags=["Inventory"])

# Raw Materials (Forms Extension)
from app.api import raw_materials
app.include_router(raw_materials.router, prefix="/api/inventory/raw-materials", tags=["Raw Materials"])

# Processing / Manufacturing (Agriculture Phase)
from app.api import processing
app.include_router(processing.router, prefix="/api/processing", tags=["Processing"])

# Automation Engine (Phase 6.1)
from app.api import automation
app.include_router(automation.router, prefix="/api", tags=["Automation"])

# Form Builder (Phase 8) - Dynamic Forms
from app.api import forms
app.include_router(forms.router, prefix="/api", tags=["Forms"])

# AI Advisory System (Phase 9)
from app.api import ai
app.include_router(ai.router, prefix="/api/ai", tags=["AI Advisory"])

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "fear-Allah API"}


@app.get("/api/health")
async def api_health_check():
    return {"status": "ok", "service": "fear-Allah API"}

# Mount Socket.IO at /socket.io (Phase 4.1)
# This keeps REST routes untouched and adds real-time via Socket.IO
app.mount("/socket.io", socket_app)
