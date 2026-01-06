"""
AI Advisory API Endpoints

Provides:
- GET /api/ai/recommendations - List AI recommendations
- POST /api/ai/run - Trigger on-demand AI analysis
- POST /api/ai/recommendations/{id}/dismiss - Dismiss a recommendation
- GET /api/ai/status - Get AI engine status and badge count
- GET /api/ai/scheduler/status - Get scheduler status (Phase 4.2)
- POST /api/ai/scheduler/trigger/{job_id} - Manually trigger a job (Phase 4.2)
- PATCH /api/ai/recommendations/{id}/governance - Update governance tags (Phase 5.1)

All endpoints are admin-only.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
import json

from app.core.security import get_current_user
from app.db.database import get_db
from app.db.models import User, AIRecommendation
from app.db.enums import (
    AIRecommendationType, AIRecommendationScope, AIGenerationMode, AIRecommendationStatus,
    AIRecommendationPriority, AIRecommendationCategory, AIRiskLevel  # Phase 5.1
)
from app.ai import (
    run_all_analysis,
    get_recommendations,
    get_recommendation_count,
    dismiss_recommendation,
    run_recommendation_engine,  # Phase 9.2
)
from app.ai.scheduler import get_scheduler_status, trigger_job  # Phase 4.2
from app.ai.safety import get_ai_safety_status  # Phase 5.1 - AI write safety
from sqlalchemy import select

router = APIRouter()


# ============================================================================
# Helper Functions
# ============================================================================

async def _check_admin(db: AsyncSession, user_id: int) -> bool:
    """Check if user is admin (system_admin or team_admin)."""
    q = select(User.is_system_admin, User.role).where(User.id == user_id)
    result = await db.execute(q)
    row = result.one_or_none()
    if not row:
        return False
    return row[0] or row[1] in ('system_admin', 'team_admin')


def _serialize_recommendation(rec: AIRecommendation) -> dict:
    """Serialize an AI recommendation to JSON-safe dict."""
    explanation = None
    if rec.explanation:
        try:
            explanation = json.loads(rec.explanation)
        except:
            explanation = [rec.explanation]
    
    data_refs = None
    if rec.data_refs:
        try:
            data_refs = json.loads(rec.data_refs)
        except:
            data_refs = {}
    
    # Parse custom tags (Phase 5.1)
    tags = None
    if rec.tags:
        try:
            tags = json.loads(rec.tags)
        except:
            tags = []
    
    return {
        "id": rec.id,
        "type": rec.type.value if rec.type else None,
        "scope": rec.scope.value if rec.scope else None,
        "confidence": rec.confidence,
        "summary": rec.summary,
        "explanation": explanation,
        "data_refs": data_refs,
        "generated_by": rec.generated_by.value if rec.generated_by else None,
        # Lifecycle status (Phase 4.1)
        "status": rec.status.value if rec.status else "pending",
        "feedback_note": rec.feedback_note,
        "feedback_by_id": rec.feedback_by_id,
        "feedback_at": rec.feedback_at.isoformat() if rec.feedback_at else None,
        # Governance tags (Phase 5.1)
        "priority": rec.priority.value if rec.priority else None,
        "category": rec.category.value if rec.category else None,
        "risk_level": rec.risk_level.value if rec.risk_level else None,
        "assigned_to_id": rec.assigned_to_id,
        "tags": tags,
        "governance_note": rec.governance_note,
        # Legacy dismissal
        "is_dismissed": rec.is_dismissed,
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
        "expires_at": rec.expires_at.isoformat() if rec.expires_at else None,
    }


# ============================================================================
# Pydantic Models
# ============================================================================

class RunAnalysisRequest(BaseModel):
    """Request to run AI analysis."""
    pass  # No parameters needed for now


class FeedbackRequest(BaseModel):
    """Request to provide feedback on a recommendation (Phase 4.1)."""
    note: Optional[str] = None  # Optional admin comment


class GovernanceTagsRequest(BaseModel):
    """Request to update governance tags on a recommendation (Phase 5.1)."""
    priority: Optional[str] = None  # critical, high, medium, low
    category: Optional[str] = None  # inventory, production, procurement, sales, operations, compliance
    risk_level: Optional[str] = None  # high_risk, medium_risk, low_risk, no_risk
    assigned_to_id: Optional[int] = None  # Admin user ID
    tags: Optional[List[str]] = None  # Custom tags
    governance_note: Optional[str] = None  # Admin notes


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/status")
async def get_ai_status(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get AI engine status and recommendation count.
    Used for "New AI Insights" badge.
    """
    user_id = current_user.get('user_id')
    if not await _check_admin(db, user_id):
        raise HTTPException(status_code=403, detail={"error": "permission_denied", "message": "Admin access required"})
    
    count = await get_recommendation_count(db, include_dismissed=False)
    
    return {
        "active_recommendations": count,
        "has_new_insights": count > 0,
        "engine_status": "ready",  # STUB: Always ready for now
        "last_auto_run": None,  # STUB: No tracking yet
    }


@router.get("/safety")
async def get_safety_status(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get AI write safety status (Phase 5.1 Governance).
    
    Returns:
    - allowed_write_tables: Tables AI is allowed to INSERT into
    - allowed_update_columns: Columns AI can modify
    - violations_detected: Count of potential safety violations
    - status: "secure" or "warning"
    """
    user_id = current_user.get('user_id')
    if not await _check_admin(db, user_id):
        raise HTTPException(status_code=403, detail={"error": "permission_denied", "message": "Admin access required"})
    
    return get_ai_safety_status()


@router.get("/recommendations")
async def list_recommendations(
    type: Optional[str] = Query(None, description="Filter by type (demand_forecast, production_plan, etc.)"),
    scope: Optional[str] = Query(None, description="Filter by scope (admin, storekeeper, agent)"),
    generated_by: Optional[str] = Query(None, description="Filter by generation mode (auto, on_demand, recommendation)"),
    category: Optional[str] = Query(None, description="Filter by category (insight or recommendation)"),
    # Governance filters (Phase 5.1)
    priority: Optional[str] = Query(None, description="Filter by priority (critical, high, medium, low)"),
    risk_level: Optional[str] = Query(None, description="Filter by risk level (high_risk, medium_risk, low_risk, no_risk)"),
    gov_category: Optional[str] = Query(None, description="Filter by governance category (inventory, production, procurement, sales, operations, compliance)"),
    assigned_to_id: Optional[int] = Query(None, description="Filter by assigned admin user ID"),
    include_dismissed: bool = Query(False, description="Include dismissed recommendations"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List AI recommendations with optional filters.
    Admin only.
    
    category filter:
    - "insight": Shows analysis results (auto, on_demand generation modes)
    - "recommendation": Shows AI suggestions (recommendation generation mode)
    """
    user_id = current_user.get('user_id')
    if not await _check_admin(db, user_id):
        raise HTTPException(status_code=403, detail={"error": "permission_denied", "message": "Admin access required"})
    
    # Parse enum filters
    rec_type = None
    if type:
        try:
            rec_type = AIRecommendationType(type)
        except ValueError:
            raise HTTPException(status_code=400, detail={"error": "invalid_type", "message": f"Invalid type: {type}"})
    
    rec_scope = None
    if scope:
        try:
            rec_scope = AIRecommendationScope(scope)
        except ValueError:
            raise HTTPException(status_code=400, detail={"error": "invalid_scope", "message": f"Invalid scope: {scope}"})
    
    gen_mode = None
    if generated_by:
        try:
            gen_mode = AIGenerationMode(generated_by)
        except ValueError:
            raise HTTPException(status_code=400, detail={"error": "invalid_generated_by", "message": f"Invalid generation mode: {generated_by}"})
    
    # Category filter maps to generation modes
    if category == "insight" and not gen_mode:
        gen_mode = "insights_only"  # Special marker
    elif category == "recommendation" and not gen_mode:
        gen_mode = AIGenerationMode.recommendation
    
    recommendations = await get_recommendations(
        db,
        rec_type=rec_type,
        scope=rec_scope,
        generated_by=gen_mode,
        include_dismissed=include_dismissed,
        # Governance filters (Phase 5.1)
        priority=priority,
        risk_level=risk_level,
        gov_category=gov_category,
        assigned_to_id=assigned_to_id,
        limit=limit,
        offset=offset,
    )
    
    return {
        "recommendations": [_serialize_recommendation(r) for r in recommendations],
        "count": len(recommendations),
        "filters": {
            "type": type,
            "scope": scope,
            "generated_by": generated_by,
            "category": category,
            "priority": priority,
            "risk_level": risk_level,
            "gov_category": gov_category,
            "assigned_to_id": assigned_to_id,
            "include_dismissed": include_dismissed,
        },
    }


@router.post("/run")
async def run_ai_analysis(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger on-demand AI analysis.
    Runs all AI modules and generates new recommendations.
    Admin only.
    """
    user_id = current_user.get('user_id')
    if not await _check_admin(db, user_id):
        raise HTTPException(status_code=403, detail={"error": "permission_denied", "message": "Admin access required"})
    
    result = await run_all_analysis(db, mode=AIGenerationMode.on_demand)
    
    return {
        "status": result.get("status", "unknown"),
        "mode": "on_demand",
        "modules": result.get("modules", {}),
        "total_recommendations": result.get("total_recommendations", 0),
        "started_at": result.get("started_at"),
        "completed_at": result.get("completed_at"),
        "message": "AI analysis completed (no recommendations yet - AI logic not implemented)",
    }


@router.post("/recommendations/run")
async def run_ai_recommendations(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate AI recommendations from existing insights.
    
    Phase 9.2 - Explainable Recommendations:
    - Reads insights from ai_recommendations table
    - Generates recommendations (production, reorder, procurement)
    - Each recommendation includes confidence + risk note
    - Does NOT execute anything - suggestions only
    
    Admin only.
    """
    user_id = current_user.get('user_id')
    if not await _check_admin(db, user_id):
        raise HTTPException(status_code=403, detail={"error": "permission_denied", "message": "Admin access required"})
    
    result = await run_recommendation_engine(db)
    
    return {
        "status": result.get("status", "unknown"),
        "mode": "recommendation",
        "recommendations_generated": result.get("recommendations_generated", 0),
        "by_type": result.get("by_type", {}),
        "started_at": result.get("started_at"),
        "completed_at": result.get("completed_at"),
        "message": f"Generated {result.get('recommendations_generated', 0)} recommendations from insights",
    }


@router.post("/recommendations/{recommendation_id}/dismiss")
async def dismiss_ai_recommendation(
    recommendation_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Dismiss an AI recommendation.
    Admin only.
    """
    user_id = current_user.get('user_id')
    if not await _check_admin(db, user_id):
        raise HTTPException(status_code=403, detail={"error": "permission_denied", "message": "Admin access required"})
    
    rec = await dismiss_recommendation(db, recommendation_id, user_id)
    
    if not rec:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": f"Recommendation {recommendation_id} not found"})
    
    return {
        "id": rec.id,
        "is_dismissed": True,
        "dismissed_at": rec.dismissed_at.isoformat() if rec.dismissed_at else None,
        "message": "Recommendation dismissed",
    }


# ============================================================================
# Lifecycle Feedback Endpoints (Phase 4.1)
# ============================================================================

@router.post("/recommendations/{recommendation_id}/acknowledge")
async def acknowledge_recommendation(
    recommendation_id: int,
    body: Optional[FeedbackRequest] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Mark a recommendation as acknowledged (admin has seen it).
    Transitions: pending → acknowledged
    Admin only.
    """
    user_id = current_user.get('user_id')
    if not await _check_admin(db, user_id):
        raise HTTPException(status_code=403, detail={"error": "permission_denied", "message": "Admin access required"})
    
    # Fetch recommendation
    query = select(AIRecommendation).where(AIRecommendation.id == recommendation_id)
    result = await db.execute(query)
    rec = result.scalar_one_or_none()
    
    if not rec:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": f"Recommendation {recommendation_id} not found"})
    
    # Can only acknowledge if pending
    if rec.status != AIRecommendationStatus.pending:
        raise HTTPException(status_code=400, detail={
            "error": "invalid_transition",
            "message": f"Cannot acknowledge recommendation in '{rec.status.value}' status. Only 'pending' recommendations can be acknowledged."
        })
    
    # Update status
    rec.status = AIRecommendationStatus.acknowledged
    rec.feedback_by_id = user_id
    rec.feedback_at = datetime.utcnow()
    if body and body.note:
        rec.feedback_note = body.note
    
    await db.commit()
    await db.refresh(rec)
    
    return {
        "id": rec.id,
        "status": rec.status.value,
        "feedback_at": rec.feedback_at.isoformat() if rec.feedback_at else None,
        "message": "Recommendation acknowledged",
    }


@router.post("/recommendations/{recommendation_id}/approve")
async def approve_recommendation(
    recommendation_id: int,
    body: Optional[FeedbackRequest] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Approve a recommendation (admin agrees with the suggestion).
    Transitions: pending|acknowledged → approved
    
    NOTE: Approval is advisory only - NO automatic execution.
    Future phases may use approved recommendations for execution.
    Admin only.
    """
    user_id = current_user.get('user_id')
    if not await _check_admin(db, user_id):
        raise HTTPException(status_code=403, detail={"error": "permission_denied", "message": "Admin access required"})
    
    # Fetch recommendation
    query = select(AIRecommendation).where(AIRecommendation.id == recommendation_id)
    result = await db.execute(query)
    rec = result.scalar_one_or_none()
    
    if not rec:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": f"Recommendation {recommendation_id} not found"})
    
    # Can approve if pending or acknowledged
    if rec.status not in [AIRecommendationStatus.pending, AIRecommendationStatus.acknowledged]:
        raise HTTPException(status_code=400, detail={
            "error": "invalid_transition",
            "message": f"Cannot approve recommendation in '{rec.status.value}' status. Only 'pending' or 'acknowledged' recommendations can be approved."
        })
    
    # Update status
    rec.status = AIRecommendationStatus.approved
    rec.feedback_by_id = user_id
    rec.feedback_at = datetime.utcnow()
    if body and body.note:
        rec.feedback_note = body.note
    
    await db.commit()
    await db.refresh(rec)
    
    return {
        "id": rec.id,
        "status": rec.status.value,
        "feedback_note": rec.feedback_note,
        "feedback_at": rec.feedback_at.isoformat() if rec.feedback_at else None,
        "message": "Recommendation approved (no automatic execution)",
    }


@router.post("/recommendations/{recommendation_id}/reject")
async def reject_recommendation(
    recommendation_id: int,
    body: Optional[FeedbackRequest] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Reject a recommendation (admin disagrees with the suggestion).
    Transitions: pending|acknowledged → rejected
    
    Optionally include a note explaining why.
    Admin only.
    """
    user_id = current_user.get('user_id')
    if not await _check_admin(db, user_id):
        raise HTTPException(status_code=403, detail={"error": "permission_denied", "message": "Admin access required"})
    
    # Fetch recommendation
    query = select(AIRecommendation).where(AIRecommendation.id == recommendation_id)
    result = await db.execute(query)
    rec = result.scalar_one_or_none()
    
    if not rec:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": f"Recommendation {recommendation_id} not found"})
    
    # Can reject if pending or acknowledged
    if rec.status not in [AIRecommendationStatus.pending, AIRecommendationStatus.acknowledged]:
        raise HTTPException(status_code=400, detail={
            "error": "invalid_transition",
            "message": f"Cannot reject recommendation in '{rec.status.value}' status. Only 'pending' or 'acknowledged' recommendations can be rejected."
        })
    
    # Update status
    rec.status = AIRecommendationStatus.rejected
    rec.feedback_by_id = user_id
    rec.feedback_at = datetime.utcnow()
    if body and body.note:
        rec.feedback_note = body.note
    
    await db.commit()
    await db.refresh(rec)
    
    return {
        "id": rec.id,
        "status": rec.status.value,
        "feedback_note": rec.feedback_note,
        "feedback_at": rec.feedback_at.isoformat() if rec.feedback_at else None,
        "message": "Recommendation rejected",
    }


@router.get("/recommendations/{recommendation_id}")
async def get_recommendation_detail(
    recommendation_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed information about a single recommendation.
    Admin only.
    """
    user_id = current_user.get('user_id')
    if not await _check_admin(db, user_id):
        raise HTTPException(status_code=403, detail={"error": "permission_denied", "message": "Admin access required"})
    
    query = select(AIRecommendation).where(AIRecommendation.id == recommendation_id)
    result = await db.execute(query)
    rec = result.scalar_one_or_none()
    
    if not rec:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": f"Recommendation {recommendation_id} not found"})
    
    return _serialize_recommendation(rec)


@router.get("/recommendations/types")
async def list_recommendation_types(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List available recommendation types for filtering.
    """
    user_id = current_user.get('user_id')
    if not await _check_admin(db, user_id):
        raise HTTPException(status_code=403, detail={"error": "permission_denied", "message": "Admin access required"})
    
    return {
        "types": [
            # Insights (Phase 9.1)
            {"value": "demand_forecast", "label": "Demand Forecast", "module": "AI-1", "category": "insight"},
            {"value": "production_plan", "label": "Production Plan", "module": "AI-2", "category": "insight"},
            {"value": "waste_alert", "label": "Waste Alert", "module": "AI-3", "category": "insight"},
            {"value": "yield_insight", "label": "Yield Insight", "module": "AI-3", "category": "insight"},
            {"value": "sales_insight", "label": "Sales Insight", "module": "AI-4", "category": "insight"},
            {"value": "agent_insight", "label": "Agent Insight", "module": "AI-4", "category": "insight"},
            # Recommendations (Phase 9.2)
            {"value": "production_recommendation", "label": "Production Recommendation", "module": "AI-R", "category": "recommendation"},
            {"value": "reorder_recommendation", "label": "Reorder Recommendation", "module": "AI-R", "category": "recommendation"},
            {"value": "procurement_recommendation", "label": "Procurement Recommendation", "module": "AI-R", "category": "recommendation"},
        ],
        "scopes": [
            {"value": "admin", "label": "Admin Only"},
            {"value": "storekeeper", "label": "Storekeeper+"},
            {"value": "agent", "label": "Agent+"},
            {"value": "system", "label": "System"},
        ],
        "generation_modes": [
            {"value": "auto", "label": "Auto-generated"},
            {"value": "on_demand", "label": "On-demand"},
            {"value": "recommendation", "label": "AI Recommendation"},
        ],
        "statuses": [
            {"value": "pending", "label": "Pending Review", "color": "gray"},
            {"value": "acknowledged", "label": "Acknowledged", "color": "blue"},
            {"value": "approved", "label": "Approved", "color": "green"},
            {"value": "rejected", "label": "Rejected", "color": "red"},
            {"value": "expired", "label": "Expired", "color": "gray"},
        ],
    }


# ============================================================================
# Scheduler Endpoints (Phase 4.2)
# ============================================================================

@router.get("/scheduler/status")
async def get_scheduler_status_endpoint(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get AI scheduler status.
    
    Returns:
    - Whether scheduler is enabled/running
    - Last run times for each job
    - List of scheduled jobs with next run times
    
    Admin only.
    """
    user_id = current_user.get('user_id')
    if not await _check_admin(db, user_id):
        raise HTTPException(status_code=403, detail={"error": "permission_denied", "message": "Admin access required"})
    
    return get_scheduler_status()


@router.post("/scheduler/trigger/{job_id}")
async def trigger_scheduler_job(
    job_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Manually trigger a scheduled job.
    
    Available jobs:
    - nightly_analysis: Run full AI analysis and recommendation generation
    - weekly_cleanup: Clean up old dismissed/expired recommendations
    - expiry_check: Check and mark expired recommendations
    
    Admin only.
    """
    user_id = current_user.get('user_id')
    if not await _check_admin(db, user_id):
        raise HTTPException(status_code=403, detail={"error": "permission_denied", "message": "Admin access required"})
    
    valid_jobs = ["nightly_analysis", "weekly_cleanup", "expiry_check"]
    if job_id not in valid_jobs:
        raise HTTPException(status_code=400, detail={
            "error": "invalid_job",
            "message": f"Invalid job ID. Valid jobs: {', '.join(valid_jobs)}",
        })
    
    result = await trigger_job(job_id)
    return result


@router.post("/scheduler/run-expiry")
async def run_expiry_check_endpoint(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Run expiry check to mark expired recommendations.
    
    This checks all recommendations with expires_at < now
    and updates their status to 'expired'.
    
    Admin only.
    """
    user_id = current_user.get('user_id')
    if not await _check_admin(db, user_id):
        raise HTTPException(status_code=403, detail={"error": "permission_denied", "message": "Admin access required"})
    
    result = await trigger_job("expiry_check")
    return result


# ============================================================================
# Governance Tags Endpoints (Phase 5.1)
# ============================================================================

@router.patch("/recommendations/{recommendation_id}/governance")
async def update_governance_tags(
    recommendation_id: int,
    body: GovernanceTagsRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update governance tags on a recommendation.
    
    Allows admins to set:
    - priority: critical, high, medium, low
    - category: inventory, production, procurement, sales, operations, compliance
    - risk_level: high_risk, medium_risk, low_risk, no_risk
    - assigned_to_id: Admin user ID to assign ownership
    - tags: Custom string tags
    - governance_note: Admin notes
    
    Admin only. Does NOT execute any actions.
    """
    user_id = current_user.get('user_id')
    if not await _check_admin(db, user_id):
        raise HTTPException(status_code=403, detail={"error": "permission_denied", "message": "Admin access required"})
    
    # Fetch recommendation
    query = select(AIRecommendation).where(AIRecommendation.id == recommendation_id)
    result = await db.execute(query)
    rec = result.scalar_one_or_none()
    
    if not rec:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": f"Recommendation {recommendation_id} not found"})
    
    # Update priority if provided
    if body.priority is not None:
        try:
            rec.priority = AIRecommendationPriority(body.priority)
        except ValueError:
            raise HTTPException(status_code=400, detail={
                "error": "invalid_priority",
                "message": f"Invalid priority. Valid values: {[p.value for p in AIRecommendationPriority]}",
            })
    
    # Update category if provided
    if body.category is not None:
        try:
            rec.category = AIRecommendationCategory(body.category)
        except ValueError:
            raise HTTPException(status_code=400, detail={
                "error": "invalid_category",
                "message": f"Invalid category. Valid values: {[c.value for c in AIRecommendationCategory]}",
            })
    
    # Update risk level if provided
    if body.risk_level is not None:
        try:
            rec.risk_level = AIRiskLevel(body.risk_level)
        except ValueError:
            raise HTTPException(status_code=400, detail={
                "error": "invalid_risk_level",
                "message": f"Invalid risk level. Valid values: {[r.value for r in AIRiskLevel]}",
            })
    
    # Update assigned_to_id if provided
    if body.assigned_to_id is not None:
        # Verify user exists and is admin
        user_query = select(User).where(User.id == body.assigned_to_id)
        user_result = await db.execute(user_query)
        target_user = user_result.scalar_one_or_none()
        if not target_user:
            raise HTTPException(status_code=400, detail={
                "error": "invalid_user",
                "message": f"User {body.assigned_to_id} not found",
            })
        rec.assigned_to_id = body.assigned_to_id
    
    # Update tags if provided
    if body.tags is not None:
        rec.tags = json.dumps(body.tags)
    
    # Update governance note if provided
    if body.governance_note is not None:
        rec.governance_note = body.governance_note
    
    await db.commit()
    await db.refresh(rec)
    
    return _serialize_recommendation(rec)


@router.get("/recommendations/{recommendation_id}/governance")
async def get_governance_tags(
    recommendation_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get governance tags for a recommendation.
    Admin only.
    """
    user_id = current_user.get('user_id')
    if not await _check_admin(db, user_id):
        raise HTTPException(status_code=403, detail={"error": "permission_denied", "message": "Admin access required"})
    
    query = select(AIRecommendation).where(AIRecommendation.id == recommendation_id)
    result = await db.execute(query)
    rec = result.scalar_one_or_none()
    
    if not rec:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": f"Recommendation {recommendation_id} not found"})
    
    tags = None
    if rec.tags:
        try:
            tags = json.loads(rec.tags)
        except:
            tags = []
    
    return {
        "id": rec.id,
        "priority": rec.priority.value if rec.priority else None,
        "category": rec.category.value if rec.category else None,
        "risk_level": rec.risk_level.value if rec.risk_level else None,
        "assigned_to_id": rec.assigned_to_id,
        "tags": tags,
        "governance_note": rec.governance_note,
    }


@router.post("/recommendations/{recommendation_id}/assign")
async def assign_recommendation(
    recommendation_id: int,
    assigned_to_id: int = Query(..., description="User ID to assign to"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Assign a recommendation to an admin user.
    Shorthand for updating governance with just assigned_to_id.
    Admin only.
    """
    user_id = current_user.get('user_id')
    if not await _check_admin(db, user_id):
        raise HTTPException(status_code=403, detail={"error": "permission_denied", "message": "Admin access required"})
    
    # Fetch recommendation
    query = select(AIRecommendation).where(AIRecommendation.id == recommendation_id)
    result = await db.execute(query)
    rec = result.scalar_one_or_none()
    
    if not rec:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": f"Recommendation {recommendation_id} not found"})
    
    # Verify target user exists
    user_query = select(User).where(User.id == assigned_to_id)
    user_result = await db.execute(user_query)
    target_user = user_result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=400, detail={
            "error": "invalid_user",
            "message": f"User {assigned_to_id} not found",
        })
    
    rec.assigned_to_id = assigned_to_id
    await db.commit()
    
    return {
        "id": rec.id,
        "assigned_to_id": rec.assigned_to_id,
        "message": f"Recommendation assigned to user {assigned_to_id}",
    }


@router.get("/governance/options")
async def get_governance_options(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get available governance tag options.
    Returns all valid values for priority, category, and risk_level.
    Admin only.
    """
    user_id = current_user.get('user_id')
    if not await _check_admin(db, user_id):
        raise HTTPException(status_code=403, detail={"error": "permission_denied", "message": "Admin access required"})
    
    return {
        "priorities": [
            {"value": "critical", "label": "Critical", "color": "red"},
            {"value": "high", "label": "High", "color": "orange"},
            {"value": "medium", "label": "Medium", "color": "yellow"},
            {"value": "low", "label": "Low", "color": "gray"},
        ],
        "categories": [
            {"value": "inventory", "label": "Inventory"},
            {"value": "production", "label": "Production"},
            {"value": "procurement", "label": "Procurement"},
            {"value": "sales", "label": "Sales"},
            {"value": "operations", "label": "Operations"},
            {"value": "compliance", "label": "Compliance"},
        ],
        "risk_levels": [
            {"value": "high_risk", "label": "High Risk", "color": "red"},
            {"value": "medium_risk", "label": "Medium Risk", "color": "orange"},
            {"value": "low_risk", "label": "Low Risk", "color": "yellow"},
            {"value": "no_risk", "label": "No Risk", "color": "green"},
        ],
    }

