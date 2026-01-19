"""
AI Scheduler (Phase 4.2)

Provides automated scheduling for AI analysis:
- Nightly analysis at 2:00 AM (configurable)
- Weekly cleanup of old recommendations
- Auto-expiry of expired recommendations

Uses APScheduler for background task management.

SAFETY: All scheduled jobs only read and write to ai_recommendations table.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
except ImportError:
    # APScheduler is an optional runtime dependency for AI scheduling; if it's not
    # installed (e.g., in lightweight test environments), avoid failing import.
    AsyncIOScheduler = None
    CronTrigger = None
    IntervalTrigger = None
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, update, delete, and_

from app.db.models import AIRecommendation
from app.db.enums import AIRecommendationStatus, AIGenerationMode
from app.core.config import settings

logger = logging.getLogger(__name__)


# ============================================================================
# Scheduler State
# ============================================================================

_scheduler: Optional[AsyncIOScheduler] = None
_last_auto_run: Optional[datetime] = None
_last_expiry_check: Optional[datetime] = None
_last_cleanup: Optional[datetime] = None
_scheduler_enabled: bool = False


def get_scheduler_status() -> dict:
    """Get current scheduler status."""
    global _scheduler
    
    jobs = []
    if _scheduler and _scheduler.running:
        for job in _scheduler.get_jobs():
            next_run = job.next_run_time
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": next_run.isoformat() if next_run else None,
            })
    
    return {
        "enabled": _scheduler_enabled,
        "running": _scheduler.running if _scheduler else False,
        "last_auto_run": _last_auto_run.isoformat() if _last_auto_run else None,
        "last_expiry_check": _last_expiry_check.isoformat() if _last_expiry_check else None,
        "last_cleanup": _last_cleanup.isoformat() if _last_cleanup else None,
        "scheduled_jobs": jobs,
    }


# ============================================================================
# Database Session Factory (for scheduled jobs)
# ============================================================================

_async_session_factory: Optional[sessionmaker] = None


def _get_async_database_url() -> str:
    """Convert sync DATABASE_URL to async URL."""
    db_url = settings.DATABASE_URL
    # Convert postgresql:// to postgresql+asyncpg://
    if db_url.startswith("postgresql://"):
        return db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return db_url


def _get_session_factory():
    """Get or create async session factory for scheduled jobs."""
    global _async_session_factory
    
    if _async_session_factory is None:
        engine = create_async_engine(
            _get_async_database_url(),
            echo=False,
            pool_pre_ping=True,
        )
        _async_session_factory = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
    
    return _async_session_factory


# ============================================================================
# Auto-Expiry Job
# ============================================================================

async def run_expiry_check() -> Dict[str, Any]:
    """
    Check and mark expired recommendations.
    
    Runs every hour to update status of recommendations past their expires_at.
    
    Flow:
        expires_at < now AND status NOT IN (expired, rejected)
        → status = expired
    """
    global _last_expiry_check
    
    logger.info("[AI Scheduler] Running expiry check")
    
    session_factory = _get_session_factory()
    expired_count = 0
    
    try:
        async with session_factory() as session:
            now = datetime.utcnow()
            
            # Find and update expired recommendations
            query = (
                update(AIRecommendation)
                .where(and_(
                    AIRecommendation.expires_at < now,
                    AIRecommendation.status.notin_([
                        AIRecommendationStatus.expired,
                        AIRecommendationStatus.rejected,
                    ])
                ))
                .values(status=AIRecommendationStatus.expired)
            )
            
            result = await session.execute(query)
            expired_count = result.rowcount
            await session.commit()
            
        _last_expiry_check = now
        
        if expired_count > 0:
            logger.info(f"[AI Scheduler] Marked {expired_count} recommendations as expired")
        
        return {
            "status": "completed",
            "expired_count": expired_count,
            "checked_at": now.isoformat(),
        }
        
    except Exception as e:
        logger.exception(f"[AI Scheduler] Expiry check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


# ============================================================================
# Nightly Analysis Job
# ============================================================================

async def run_nightly_analysis() -> Dict[str, Any]:
    """
    Run nightly AI analysis.
    
    Scheduled to run at 2:00 AM daily.
    
    1. Runs all AI analyzers (insights)
    2. Generates recommendations from insights
    3. Runs expiry check
    """
    global _last_auto_run
    
    logger.info("[AI Scheduler] Starting nightly analysis")
    
    session_factory = _get_session_factory()
    results = {
        "started_at": datetime.utcnow().isoformat(),
        "insights": {},
        "recommendations": {},
        "expiry": {},
    }
    
    try:
        async with session_factory() as session:
            # Import here to avoid circular imports
            from app.ai.engine import run_all_analysis
            from app.ai.recommender import run_recommendation_engine
            
            # Step 1: Run all analyzers to generate insights
            logger.info("[AI Scheduler] Running analyzers...")
            insights_result = await run_all_analysis(session, mode=AIGenerationMode.auto)
            results["insights"] = insights_result
            
            # Step 2: Generate recommendations from insights
            logger.info("[AI Scheduler] Generating recommendations...")
            rec_result = await run_recommendation_engine(session)
            results["recommendations"] = rec_result
        
        # Step 3: Run expiry check
        logger.info("[AI Scheduler] Running expiry check...")
        expiry_result = await run_expiry_check()
        results["expiry"] = expiry_result
        
        _last_auto_run = datetime.utcnow()
        results["completed_at"] = _last_auto_run.isoformat()
        results["status"] = "completed"
        
        logger.info(f"[AI Scheduler] Nightly analysis complete: {results['insights'].get('total_recommendations', 0)} insights, {results['recommendations'].get('recommendations_generated', 0)} recommendations")
        
    except Exception as e:
        logger.exception(f"[AI Scheduler] Nightly analysis failed: {e}")
        results["status"] = "error"
        results["error"] = str(e)
    
    return results


# ============================================================================
# Weekly Cleanup Job
# ============================================================================

async def run_weekly_cleanup() -> Dict[str, Any]:
    """
    Clean up old recommendations.
    
    Scheduled to run weekly on Sundays at 3:00 AM.
    
    Deletes:
    - Dismissed recommendations older than 7 days
    - Expired recommendations older than 30 days
    - Rejected recommendations older than 30 days
    """
    global _last_cleanup
    
    logger.info("[AI Scheduler] Starting weekly cleanup")
    
    session_factory = _get_session_factory()
    
    try:
        async with session_factory() as session:
            now = datetime.utcnow()
            
            # Delete dismissed older than 7 days
            dismissed_cutoff = now - timedelta(days=7)
            dismissed_query = (
                delete(AIRecommendation)
                .where(and_(
                    AIRecommendation.is_dismissed == True,
                    AIRecommendation.dismissed_at < dismissed_cutoff
                ))
            )
            dismissed_result = await session.execute(dismissed_query)
            dismissed_count = dismissed_result.rowcount
            
            # Delete expired older than 30 days
            expired_cutoff = now - timedelta(days=30)
            expired_query = (
                delete(AIRecommendation)
                .where(and_(
                    AIRecommendation.status == AIRecommendationStatus.expired,
                    AIRecommendation.expires_at < expired_cutoff
                ))
            )
            expired_result = await session.execute(expired_query)
            expired_count = expired_result.rowcount
            
            # Delete rejected older than 30 days
            rejected_query = (
                delete(AIRecommendation)
                .where(and_(
                    AIRecommendation.status == AIRecommendationStatus.rejected,
                    AIRecommendation.feedback_at < expired_cutoff
                ))
            )
            rejected_result = await session.execute(rejected_query)
            rejected_count = rejected_result.rowcount
            
            await session.commit()
            
        _last_cleanup = now
        total_deleted = dismissed_count + expired_count + rejected_count
        
        logger.info(f"[AI Scheduler] Weekly cleanup complete: {total_deleted} records deleted (dismissed: {dismissed_count}, expired: {expired_count}, rejected: {rejected_count})")
        
        return {
            "status": "completed",
            "deleted": {
                "dismissed": dismissed_count,
                "expired": expired_count,
                "rejected": rejected_count,
                "total": total_deleted,
            },
            "cleaned_at": now.isoformat(),
        }
        
    except Exception as e:
        logger.exception(f"[AI Scheduler] Weekly cleanup failed: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


# ============================================================================
# Scheduler Setup & Shutdown
# ============================================================================

def setup_scheduler(
    nightly_hour: int = 2,
    nightly_minute: int = 0,
    cleanup_day: str = "sun",
    cleanup_hour: int = 3,
    expiry_interval_hours: int = 1,
):
    """
    Initialize the AI scheduler.
    
    Args:
        nightly_hour: Hour to run nightly analysis (0-23)
        nightly_minute: Minute to run nightly analysis (0-59)
        cleanup_day: Day of week for cleanup (mon, tue, wed, thu, fri, sat, sun)
        cleanup_hour: Hour to run weekly cleanup (0-23)
        expiry_interval_hours: How often to check for expired recommendations
    """
    global _scheduler, _scheduler_enabled
    
    if _scheduler is not None and _scheduler.running:
        logger.warning("[AI Scheduler] Scheduler already running")
        return
    
    logger.info("[AI Scheduler] Setting up scheduler...")
    
    _scheduler = AsyncIOScheduler()
    
    # Nightly analysis job (2:00 AM by default)
    _scheduler.add_job(
        run_nightly_analysis,
        CronTrigger(hour=nightly_hour, minute=nightly_minute),
        id="nightly_analysis",
        name="Nightly AI Analysis",
        replace_existing=True,
    )
    
    # Weekly cleanup job (Sunday 3:00 AM by default)
    _scheduler.add_job(
        run_weekly_cleanup,
        CronTrigger(day_of_week=cleanup_day, hour=cleanup_hour, minute=0),
        id="weekly_cleanup",
        name="Weekly Recommendation Cleanup",
        replace_existing=True,
    )
    
    # Expiry check job (every hour by default)
    _scheduler.add_job(
        run_expiry_check,
        IntervalTrigger(hours=expiry_interval_hours),
        id="expiry_check",
        name="Recommendation Expiry Check",
        replace_existing=True,
    )
    
    _scheduler.start()
    _scheduler_enabled = True
    
    logger.info(f"[AI Scheduler] Started with jobs: nightly at {nightly_hour:02d}:{nightly_minute:02d}, cleanup on {cleanup_day} at {cleanup_hour:02d}:00, expiry check every {expiry_interval_hours}h")


def shutdown_scheduler():
    """Shutdown the AI scheduler gracefully."""
    global _scheduler, _scheduler_enabled
    
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        logger.info("[AI Scheduler] Scheduler shutdown")
    
    _scheduler = None
    _scheduler_enabled = False


async def trigger_job(job_id: str) -> Dict[str, Any]:
    """
    Manually trigger a scheduled job.
    
    Args:
        job_id: One of "nightly_analysis", "weekly_cleanup", "expiry_check"
    
    Returns:
        Job result
    """
    if job_id == "nightly_analysis":
        return await run_nightly_analysis()
    elif job_id == "weekly_cleanup":
        return await run_weekly_cleanup()
    elif job_id == "expiry_check":
        return await run_expiry_check()
    else:
        return {"status": "error", "message": f"Unknown job: {job_id}"}
