"""
AI Advisory Engine (Phase 9)

This module contains the AI advisory system that:
- Observes business data (sales, inventory, production)
- Analyzes patterns and anomalies
- Generates INSIGHTS (facts + explanations)
- Later: Recommends actions (Phase 9.2)

SAFETY GUARANTEE:
- AI reads from: sales, inventory, raw_materials, processing_batches, recipes
- AI writes ONLY to: ai_recommendations table
- AI NEVER mutates core business tables (orders, inventory, etc.)

Phase 9.1: Read Models (Insights)
- Sales velocity analysis
- Inventory coverage days
- Raw material burn rate
- Production yield averages
- Waste baselines

Output format:
{
    "type": "insight",
    "summary": "Factual statement about what happened",
    "explanation": ["Supporting fact 1", "Supporting fact 2"],
    "confidence": 0.0 - 1.0
}

❌ No "produce X" recommendations yet
❌ No "order Y" advice yet
✅ Just facts + explanations
"""
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.db.models import AIRecommendation
from app.db.enums import AIRecommendationType, AIRecommendationScope, AIGenerationMode
from app.ai.analyzers import run_all_analyzers

logger = logging.getLogger(__name__)


# ============================================================================
# Exceptions
# ============================================================================

class AIEngineError(Exception):
    """Base exception for AI engine errors."""
    pass


class AIAnalysisError(AIEngineError):
    """Error during AI analysis."""
    pass


# ============================================================================
# Helper: Save Insights to Database
# ============================================================================

async def save_insights_to_db(
    session: AsyncSession,
    insights: List[Dict[str, Any]],
    mode: AIGenerationMode,
    scope: AIRecommendationScope = AIRecommendationScope.admin,
) -> List[AIRecommendation]:
    """
    Save computed insights to the ai_recommendations table.
    
    Each insight dict should have:
    - type: AIRecommendationType
    - summary: str
    - explanation: List[str]
    - confidence: float (0.0-1.0)
    - data_refs: dict (optional)
    """
    saved = []
    
    for insight in insights:
        rec = AIRecommendation(
            type=insight["type"],
            scope=scope,
            confidence=insight.get("confidence", 0.5),
            summary=insight["summary"],
            explanation=json.dumps(insight.get("explanation", [])),
            data_refs=json.dumps(insight.get("data_refs", {})),
            generated_by=mode,
            expires_at=datetime.utcnow() + timedelta(days=7),  # Insights expire in 7 days
        )
        session.add(rec)
        saved.append(rec)
    
    if saved:
        await session.commit()
        logger.info(f"[AI Engine] Saved {len(saved)} insights to database")
    
    return saved


# ============================================================================
# AI-1: Demand Forecasting (Now with insights)
# ============================================================================

async def run_demand_forecast(
    session: AsyncSession,
    mode: AIGenerationMode = AIGenerationMode.auto,
) -> List[AIRecommendation]:
    """
    Generate demand forecasts and inventory coverage insights.
    
    Phase 9.1: Read-only insights
    - Sales velocity changes
    - Inventory coverage days
    - Raw material burn rates
    
    Phase 9.2 (TODO): Add recommendations
    - "Reorder X units"
    - "Increase production"
    """
    logger.info("[AI-1] Running demand forecast analysis")
    
    from app.ai.analyzers import (
        analyze_sales_velocity,
        analyze_inventory_coverage,
        analyze_raw_material_burn_rate
    )
    
    insights = []
    
    # Sales velocity insights
    try:
        velocity = await analyze_sales_velocity(session)
        insights.extend(velocity)
    except Exception as e:
        logger.error(f"[AI-1] Sales velocity failed: {e}")
    
    # Inventory coverage insights  
    try:
        coverage = await analyze_inventory_coverage(session)
        insights.extend(coverage)
    except Exception as e:
        logger.error(f"[AI-1] Inventory coverage failed: {e}")
    
    # Raw material burn rate
    try:
        burn_rate = await analyze_raw_material_burn_rate(session)
        insights.extend(burn_rate)
    except Exception as e:
        logger.error(f"[AI-1] Burn rate analysis failed: {e}")
    
    # Save insights to database
    saved = await save_insights_to_db(session, insights, mode)
    
    return saved


# ============================================================================
# AI-2: Production Planning Advisor (STUB - Phase 9.2)
# ============================================================================

async def run_production_advisor(
    session: AsyncSession,
    mode: AIGenerationMode = AIGenerationMode.auto,
) -> List[AIRecommendation]:
    """
    Generate production planning recommendations.
    
    Phase 9.1: No output yet (recommendations not insights)
    Phase 9.2 (TODO): Add recommendations
    - "Produce X units"
    - "Schedule batch for tomorrow"
    """
    logger.info("[AI-2] Production advisor - skipped (Phase 9.2)")
    
    # Phase 9.2 will add production recommendations here
    # For now, return empty - we don't give advice yet
    return []


# ============================================================================
# AI-3: Waste & Yield Intelligence (Now with insights)
# ============================================================================

async def run_waste_analysis(
    session: AsyncSession,
    mode: AIGenerationMode = AIGenerationMode.auto,
) -> List[AIRecommendation]:
    """
    Detect waste anomalies and yield efficiency patterns.
    
    Phase 9.1: Read-only insights
    - Yield efficiency averages
    - Waste baselines
    - Anomaly detection
    
    Phase 9.2 (TODO): Add recommendations
    - "Review batch process"
    - "Investigate waste spike"
    """
    logger.info("[AI-3] Running waste & yield analysis")
    
    from app.ai.analyzers import analyze_production_yields, analyze_waste_baselines
    
    insights = []
    
    # Production yield insights
    try:
        yields = await analyze_production_yields(session)
        insights.extend(yields)
    except Exception as e:
        logger.error(f"[AI-3] Yield analysis failed: {e}")
    
    # Waste baseline insights
    try:
        waste = await analyze_waste_baselines(session)
        insights.extend(waste)
    except Exception as e:
        logger.error(f"[AI-3] Waste analysis failed: {e}")
    
    # Save insights to database
    saved = await save_insights_to_db(session, insights, mode)
    
    return saved


# ============================================================================
# AI-4: Sales & Agent Intelligence (STUB - Phase 9.2)
# ============================================================================

async def run_sales_intelligence(
    session: AsyncSession,
    mode: AIGenerationMode = AIGenerationMode.auto,
) -> List[AIRecommendation]:
    """
    Generate sales and agent performance insights.
    
    Phase 9.1: Sales velocity already covered in AI-1
    Phase 9.2 (TODO): Add agent-specific insights
    - Agent performance comparisons
    - Channel analysis
    """
    logger.info("[AI-4] Sales intelligence - covered by AI-1")
    
    # Sales velocity is already in AI-1
    # Phase 9.2 will add agent-specific analytics
    return []


# ============================================================================
# Master Analysis Runner
# ============================================================================

async def run_all_analysis(
    session: AsyncSession,
    mode: AIGenerationMode = AIGenerationMode.auto,
) -> Dict[str, Any]:
    """
    Run all AI analysis modules.
    
    Called by:
    - Nightly cron job (mode=auto)
    - Manual "Run AI Analysis" button (mode=on_demand)
    
    Phase 9.1: Generates INSIGHTS (facts only)
    Phase 9.2: Will add RECOMMENDATIONS (advice)
    
    Returns summary of generated insights.
    """
    logger.info(f"[AI Engine] Running all analysis (mode={mode.value})")
    
    results = {
        "mode": mode.value,
        "started_at": datetime.utcnow().isoformat(),
        "modules": {},
        "total_recommendations": 0,
        "insights_generated": 0,
    }
    
    try:
        # Clear old insights from this run type to avoid duplicates
        # Only clear non-dismissed insights
        await session.execute(
            delete(AIRecommendation).where(
                AIRecommendation.is_dismissed == False,
                AIRecommendation.generated_by == mode
            )
        )
        await session.commit()
        
        # Run each module
        demand_recs = await run_demand_forecast(session, mode)
        results["modules"]["demand_forecast"] = len(demand_recs)
        
        production_recs = await run_production_advisor(session, mode)
        results["modules"]["production_advisor"] = len(production_recs)
        
        waste_recs = await run_waste_analysis(session, mode)
        results["modules"]["waste_analysis"] = len(waste_recs)
        
        sales_recs = await run_sales_intelligence(session, mode)
        results["modules"]["sales_intelligence"] = len(sales_recs)
        
        # Calculate total
        all_recs = demand_recs + production_recs + waste_recs + sales_recs
        results["total_recommendations"] = len(all_recs)
        results["insights_generated"] = len(all_recs)
        
        results["completed_at"] = datetime.utcnow().isoformat()
        results["status"] = "completed"
        
        logger.info(f"[AI Engine] Analysis complete: {results['total_recommendations']} recommendations")
        
    except Exception as e:
        logger.exception(f"[AI Engine] Error during analysis: {e}")
        results["status"] = "error"
        results["error"] = str(e)
    
    return results


# ============================================================================
# Recommendation Management
# ============================================================================

async def get_recommendations(
    session: AsyncSession,
    rec_type: Optional[AIRecommendationType] = None,
    scope: Optional[AIRecommendationScope] = None,
    generated_by: Optional[AIGenerationMode] = None,
    include_dismissed: bool = False,
    # Governance filters (Phase 5.1)
    priority: Optional[str] = None,
    risk_level: Optional[str] = None,
    gov_category: Optional[str] = None,
    assigned_to_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[AIRecommendation]:
    """
    Get AI recommendations with optional filters.
    
    generated_by:
    - AIGenerationMode enum: Filter to specific mode
    - "insights_only" string: Filter to auto + on_demand (not recommendations)
    
    Governance filters (Phase 5.1):
    - priority: critical, high, medium, low
    - risk_level: high_risk, medium_risk, low_risk, no_risk
    - gov_category: inventory, production, procurement, sales, operations, compliance
    - assigned_to_id: Admin user ID
    """
    query = select(AIRecommendation).order_by(AIRecommendation.created_at.desc())
    
    if rec_type:
        query = query.where(AIRecommendation.type == rec_type)
    if scope:
        query = query.where(AIRecommendation.scope == scope)
    if generated_by:
        if generated_by == "insights_only":
            # Special case: show only insights (auto or on_demand), not recommendations
            query = query.where(AIRecommendation.generated_by.in_([
                AIGenerationMode.auto,
                AIGenerationMode.on_demand
            ]))
        else:
            query = query.where(AIRecommendation.generated_by == generated_by)
    if not include_dismissed:
        query = query.where(AIRecommendation.is_dismissed == False)
    
    # Governance filters (Phase 5.1)
    if priority:
        from app.db.enums import AIRecommendationPriority
        try:
            priority_enum = AIRecommendationPriority(priority)
            query = query.where(AIRecommendation.priority == priority_enum)
        except ValueError:
            pass  # Invalid priority, ignore filter
    
    if risk_level:
        from app.db.enums import AIRiskLevel
        try:
            risk_enum = AIRiskLevel(risk_level)
            query = query.where(AIRecommendation.risk_level == risk_enum)
        except ValueError:
            pass  # Invalid risk level, ignore filter
    
    if gov_category:
        from app.db.enums import AIRecommendationCategory
        try:
            category_enum = AIRecommendationCategory(gov_category)
            query = query.where(AIRecommendation.category == category_enum)
        except ValueError:
            pass  # Invalid category, ignore filter
    
    if assigned_to_id is not None:
        query = query.where(AIRecommendation.assigned_to_id == assigned_to_id)
    
    # Filter expired recommendations
    query = query.where(
        (AIRecommendation.expires_at == None) | 
        (AIRecommendation.expires_at > datetime.utcnow())
    )
    
    query = query.limit(limit).offset(offset)
    
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_recommendation_count(
    session: AsyncSession,
    include_dismissed: bool = False,
) -> int:
    """
    Get count of active (non-dismissed, non-expired) recommendations.
    Used for "New AI Insights" badge.
    """
    from sqlalchemy import func
    
    query = select(func.count(AIRecommendation.id))
    
    if not include_dismissed:
        query = query.where(AIRecommendation.is_dismissed == False)
    
    query = query.where(
        (AIRecommendation.expires_at == None) | 
        (AIRecommendation.expires_at > datetime.utcnow())
    )
    
    result = await session.execute(query)
    return result.scalar() or 0


async def dismiss_recommendation(
    session: AsyncSession,
    recommendation_id: int,
    dismissed_by_id: int,
) -> Optional[AIRecommendation]:
    """
    Mark a recommendation as dismissed.
    """
    result = await session.execute(
        select(AIRecommendation).where(AIRecommendation.id == recommendation_id)
    )
    rec = result.scalar_one_or_none()
    
    if not rec:
        return None
    
    rec.is_dismissed = True
    rec.dismissed_by_id = dismissed_by_id
    rec.dismissed_at = datetime.utcnow()
    
    await session.commit()
    await session.refresh(rec)
    
    return rec


async def clear_old_recommendations(
    session: AsyncSession,
    days_old: int = 30,
) -> int:
    """
    Remove recommendations older than specified days.
    Called by maintenance job.
    """
    cutoff = datetime.utcnow() - timedelta(days=days_old)
    
    result = await session.execute(
        delete(AIRecommendation).where(AIRecommendation.created_at < cutoff)
    )
    await session.commit()
    
    deleted_count = result.rowcount
    logger.info(f"[AI Engine] Cleared {deleted_count} old recommendations (>{days_old} days)")
    
    return deleted_count
