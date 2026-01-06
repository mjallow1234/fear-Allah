"""
AI Recommendation Engine (Phase 9.2 + Phase 4.2 Deduplication)

Converts insights (facts) → recommendations (suggestions).

HARD CONSTRAINTS:
- NO automatic execution
- NO inventory updates
- NO order creation
- NO task creation
- Admin-only visibility
- AI writes ONLY to ai_recommendations table

Flow:
    Sales / Inventory / Production Data
            ↓
    AI Phase 2 Analyzers (facts)
            ↓
    Insight records (already implemented)
            ↓
    AI Phase 3 Recommendation Engine (THIS FILE)

Every recommendation MUST include:
- Supporting insights (data_refs.insight_ids)
- Reasoning chain (explanation[])
- Confidence score (0.0-1.0)
- Risk note (explanation[-1])
"""
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.db.models import AIRecommendation, Inventory, RawMaterial
from app.db.enums import (
    AIRecommendationType, 
    AIRecommendationScope, 
    AIGenerationMode,
    AIRecommendationStatus,
    ProductType
)

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================

# Thresholds for triggering recommendations
INVENTORY_COVERAGE_CRITICAL_DAYS = 7  # Low stock alert threshold
INVENTORY_COVERAGE_WARNING_DAYS = 14  # Warning threshold
RAW_MATERIAL_COVERAGE_CRITICAL_DAYS = 10  # Raw material alert
SALES_INCREASE_THRESHOLD_PCT = 15  # Minimum sales increase to trigger production recommendation
MIN_CONFIDENCE_FOR_RECOMMENDATION = 0.4  # Don't recommend if confidence below this


# ============================================================================
# Helper: Load Recent Insights
# ============================================================================

async def load_recent_insights(
    session: AsyncSession,
    insight_types: List[AIRecommendationType],
    max_age_days: int = 7,
) -> List[AIRecommendation]:
    """
    Load recent insights from the database.
    Only loads non-dismissed, non-expired insights.
    """
    cutoff = datetime.utcnow() - timedelta(days=max_age_days)
    
    query = (
        select(AIRecommendation)
        .where(and_(
            AIRecommendation.type.in_(insight_types),
            AIRecommendation.is_dismissed == False,
            AIRecommendation.created_at >= cutoff,
            AIRecommendation.generated_by.in_([
                AIGenerationMode.auto, 
                AIGenerationMode.on_demand
            ])  # Only insights, not recommendations
        ))
        .order_by(AIRecommendation.created_at.desc())
    )
    
    result = await session.execute(query)
    return list(result.scalars().all())


def parse_insight_data_refs(insight: AIRecommendation) -> Dict[str, Any]:
    """Parse data_refs JSON from an insight."""
    if not insight.data_refs:
        return {}
    try:
        return json.loads(insight.data_refs)
    except:
        return {}


def parse_insight_explanation(insight: AIRecommendation) -> List[str]:
    """Parse explanation JSON from an insight."""
    if not insight.explanation:
        return []
    try:
        return json.loads(insight.explanation)
    except:
        return [insight.explanation] if isinstance(insight.explanation, str) else []


# ============================================================================
# Production Recommendation Generator
# ============================================================================

async def generate_production_recommendations(
    session: AsyncSession,
    insights: List[AIRecommendation],
) -> List[Dict[str, Any]]:
    """
    Generate production recommendations based on:
    - Sales velocity increasing
    - Inventory coverage decreasing
    - Raw materials sufficient
    
    Trigger conditions:
    - Sales increased > 15%
    - Inventory coverage < 14 days
    - Have raw materials for production
    """
    logger.info("[RecommendationEngine] Generating production recommendations")
    
    recommendations = []
    
    # Group insights by product
    product_insights: Dict[int, Dict[str, List[AIRecommendation]]] = {}
    
    for insight in insights:
        data_refs = parse_insight_data_refs(insight)
        product_id = data_refs.get("product_id")
        if not product_id:
            continue
        
        if product_id not in product_insights:
            product_insights[product_id] = {
                "sales": [],
                "coverage": [],
                "yield": [],
            }
        
        if insight.type == AIRecommendationType.sales_insight:
            product_insights[product_id]["sales"].append(insight)
        elif insight.type == AIRecommendationType.demand_forecast:
            product_insights[product_id]["coverage"].append(insight)
        elif insight.type == AIRecommendationType.yield_insight:
            product_insights[product_id]["yield"].append(insight)
    
    # Analyze each product
    for product_id, categorized in product_insights.items():
        sales_insights = categorized["sales"]
        coverage_insights = categorized["coverage"]
        
        if not sales_insights and not coverage_insights:
            continue
        
        # Check for sales increase
        sales_increasing = False
        sales_pct_change = 0
        product_name = f"Product {product_id}"
        
        for si in sales_insights:
            if "increased" in si.summary.lower():
                sales_increasing = True
                # Extract percentage from summary like "Widget A sales increased 100% this period"
                try:
                    parts = si.summary.split("increased")
                    if len(parts) > 1:
                        pct_str = parts[1].strip().split("%")[0]
                        sales_pct_change = float(pct_str)
                except:
                    sales_pct_change = 20  # Default if parsing fails
                
                data_refs = parse_insight_data_refs(si)
                product_name = data_refs.get("product_name", product_name)
                break
        
        # Check for low coverage
        low_coverage = False
        coverage_days = None
        
        for ci in coverage_insights:
            data_refs = parse_insight_data_refs(ci)
            coverage_days = data_refs.get("coverage_days")
            if coverage_days and coverage_days < INVENTORY_COVERAGE_WARNING_DAYS:
                low_coverage = True
                product_name = data_refs.get("product_name", product_name)
                break
        
        # Decide if we should recommend production
        should_recommend = False
        reasoning = []
        risk_note = None
        
        if sales_increasing and sales_pct_change >= SALES_INCREASE_THRESHOLD_PCT:
            should_recommend = True
            reasoning.append(f"Sales increased {sales_pct_change:.0f}% recently")
        
        if low_coverage and coverage_days:
            should_recommend = True
            reasoning.append(f"Only {coverage_days:.0f} days of inventory coverage")
        
        if not should_recommend:
            continue
        
        # Add yield context if available
        yield_insights = categorized.get("yield", [])
        avg_yield = None
        for yi in yield_insights:
            data_refs = parse_insight_data_refs(yi)
            avg_yield = data_refs.get("average_yield")
            if avg_yield:
                reasoning.append(f"Historical yield efficiency: {avg_yield:.0f}%")
                if avg_yield < 80:
                    risk_note = "⚠️ Production yield is below 80% - actual output may vary"
                break
        
        # Calculate confidence
        confidence = 0.5
        insight_count = len(sales_insights) + len(coverage_insights)
        if insight_count >= 3:
            confidence = 0.7
        if insight_count >= 5:
            confidence = 0.85
        if sales_increasing and low_coverage:
            confidence = min(confidence + 0.1, 0.95)
        
        # Add risk note if not already set
        if not risk_note:
            if sales_pct_change > 50:
                risk_note = "⚠️ Large sales spike - may be seasonal or one-time event"
            else:
                risk_note = "📊 Based on recent trends - monitor actual sales"
        
        reasoning.append(risk_note)
        
        # Build recommendation
        recommendations.append({
            "type": AIRecommendationType.production_recommendation,
            "summary": f"Consider increasing {product_name} production this week",
            "explanation": reasoning,
            "confidence": confidence,
            "data_refs": {
                "product_id": product_id,
                "product_name": product_name,
                "sales_pct_change": sales_pct_change,
                "coverage_days": coverage_days,
                "insight_ids": [i.id for i in sales_insights + coverage_insights],
                "recommendation_type": "production",
            }
        })
    
    logger.info(f"[RecommendationEngine] Generated {len(recommendations)} production recommendations")
    return recommendations


# ============================================================================
# Inventory Reorder Recommendation Generator
# ============================================================================

async def generate_reorder_recommendations(
    session: AsyncSession,
    insights: List[AIRecommendation],
) -> List[Dict[str, Any]]:
    """
    Generate inventory reorder recommendations based on:
    - Inventory coverage < threshold
    - Sales stable or rising
    
    Does NOT execute any orders - just suggests.
    """
    logger.info("[RecommendationEngine] Generating reorder recommendations")
    
    recommendations = []
    
    # Find low coverage insights
    for insight in insights:
        if insight.type != AIRecommendationType.demand_forecast:
            continue
        
        data_refs = parse_insight_data_refs(insight)
        coverage_days = data_refs.get("coverage_days")
        product_name = data_refs.get("product_name", "Unknown Product")
        product_id = data_refs.get("product_id")
        current_stock = data_refs.get("current_stock", 0)
        daily_avg = data_refs.get("daily_average_sales", 0)
        
        # Skip if coverage is sufficient
        if coverage_days is None or coverage_days >= INVENTORY_COVERAGE_WARNING_DAYS:
            continue
        
        # Skip if no sales (infinite coverage issue)
        if daily_avg == 0:
            continue
        
        reasoning = [
            f"Current stock: {current_stock} units",
            f"Average daily sales: {daily_avg:.1f} units",
            f"Stock will deplete in ~{coverage_days:.0f} days at current rate",
        ]
        
        # Determine urgency
        if coverage_days < INVENTORY_COVERAGE_CRITICAL_DAYS:
            urgency = "urgent"
            summary = f"Urgent: Restock {product_name} within {coverage_days:.0f} days"
            risk_note = "⚠️ Critical stock level - prioritize restocking"
            confidence = 0.85
        else:
            urgency = "normal"
            summary = f"Consider restocking {product_name} soon"
            risk_note = "📊 Stock level decreasing - plan restock within 2 weeks"
            confidence = 0.7
        
        reasoning.append(risk_note)
        
        recommendations.append({
            "type": AIRecommendationType.reorder_recommendation,
            "summary": summary,
            "explanation": reasoning,
            "confidence": confidence,
            "data_refs": {
                "product_id": product_id,
                "product_name": product_name,
                "coverage_days": coverage_days,
                "current_stock": current_stock,
                "daily_average_sales": daily_avg,
                "urgency": urgency,
                "insight_ids": [insight.id],
                "recommendation_type": "reorder",
            }
        })
    
    logger.info(f"[RecommendationEngine] Generated {len(recommendations)} reorder recommendations")
    return recommendations


# ============================================================================
# Raw Material Procurement Recommendation Generator
# ============================================================================

async def generate_procurement_recommendations(
    session: AsyncSession,
    insights: List[AIRecommendation],
) -> List[Dict[str, Any]]:
    """
    Generate raw material procurement recommendations based on:
    - Burn rate increasing
    - Coverage days falling below threshold
    
    Does NOT execute any purchases - just suggests.
    """
    logger.info("[RecommendationEngine] Generating procurement recommendations")
    
    recommendations = []
    
    # Find raw material burn rate insights
    for insight in insights:
        # Look for demand_forecast type with raw_material_id
        if insight.type != AIRecommendationType.demand_forecast:
            continue
        
        data_refs = parse_insight_data_refs(insight)
        
        # Check if this is a raw material insight
        raw_material_id = data_refs.get("raw_material_id")
        raw_material_name = data_refs.get("raw_material_name")
        
        if not raw_material_id:
            continue
        
        coverage_days = data_refs.get("coverage_days")
        current_stock = data_refs.get("current_stock")
        daily_burn = data_refs.get("daily_burn_rate", 0)
        unit = data_refs.get("unit", "units")
        
        if coverage_days is None or coverage_days >= RAW_MATERIAL_COVERAGE_CRITICAL_DAYS:
            continue
        
        reasoning = [
            f"Current stock: {current_stock} {unit}",
            f"Daily consumption rate: {daily_burn:.1f} {unit}/day",
            f"Stock will deplete in ~{coverage_days:.0f} days",
        ]
        
        # Determine urgency and risk
        if coverage_days < 7:
            risk_note = "⚠️ Critical - may halt production if not restocked"
            confidence = 0.9
            summary = f"Critical: {raw_material_name} stock may run out in {coverage_days:.0f} days"
        else:
            risk_note = "📊 Plan procurement within lead time"
            confidence = 0.75
            summary = f"{raw_material_name} stock may fall below safe levels in {coverage_days:.0f} days"
        
        reasoning.append(risk_note)
        
        recommendations.append({
            "type": AIRecommendationType.procurement_recommendation,
            "summary": summary,
            "explanation": reasoning,
            "confidence": confidence,
            "data_refs": {
                "raw_material_id": raw_material_id,
                "raw_material_name": raw_material_name,
                "coverage_days": coverage_days,
                "current_stock": current_stock,
                "daily_burn_rate": daily_burn,
                "unit": unit,
                "insight_ids": [insight.id],
                "recommendation_type": "procurement",
            }
        })
    
    logger.info(f"[RecommendationEngine] Generated {len(recommendations)} procurement recommendations")
    return recommendations


# ============================================================================
# Deduplication Logic (Phase 4.2)
# ============================================================================

async def find_duplicate_recommendation(
    session: AsyncSession,
    rec_type: AIRecommendationType,
    product_id: Optional[int] = None,
    raw_material_id: Optional[int] = None,
    max_age_days: int = 7,
) -> Optional[AIRecommendation]:
    """
    Check if a similar recommendation already exists.
    
    A recommendation is considered duplicate if:
    - Same type
    - Same product_id OR raw_material_id (for applicable types)
    - Not dismissed, rejected, or expired
    - Created within max_age_days
    
    Returns existing duplicate or None.
    """
    cutoff = datetime.utcnow() - timedelta(days=max_age_days)
    
    # Build base query
    query = (
        select(AIRecommendation)
        .where(and_(
            AIRecommendation.type == rec_type,
            AIRecommendation.generated_by == AIGenerationMode.recommendation,
            AIRecommendation.is_dismissed == False,
            AIRecommendation.status.notin_([
                AIRecommendationStatus.rejected,
                AIRecommendationStatus.expired,
            ]),
            AIRecommendation.created_at >= cutoff,
        ))
        .limit(50)  # Check recent recommendations only
    )
    
    result = await session.execute(query)
    candidates = list(result.scalars().all())
    
    # Check each candidate for matching entity
    for candidate in candidates:
        try:
            cand_refs = json.loads(candidate.data_refs) if candidate.data_refs else {}
        except:
            continue
        
        # Match by product_id
        if product_id and cand_refs.get("product_id") == product_id:
            return candidate
        
        # Match by raw_material_id
        if raw_material_id and cand_refs.get("raw_material_id") == raw_material_id:
            return candidate
    
    return None


async def deduplicate_recommendations(
    session: AsyncSession,
    recommendations: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Filter out recommendations that already exist in the database.
    
    Returns only new, non-duplicate recommendations.
    """
    logger.info(f"[Deduplication] Checking {len(recommendations)} recommendations for duplicates")
    
    unique = []
    duplicate_count = 0
    
    for rec in recommendations:
        data_refs = rec.get("data_refs", {})
        product_id = data_refs.get("product_id")
        raw_material_id = data_refs.get("raw_material_id")
        
        # Check for existing duplicate
        duplicate = await find_duplicate_recommendation(
            session,
            rec["type"],
            product_id=product_id,
            raw_material_id=raw_material_id,
        )
        
        if duplicate:
            logger.debug(f"[Deduplication] Skipping duplicate: {rec['summary'][:50]}...")
            duplicate_count += 1
        else:
            unique.append(rec)
    
    logger.info(f"[Deduplication] Filtered {duplicate_count} duplicates, {len(unique)} unique recommendations")
    return unique


# ============================================================================
# Master Recommendation Generator
# ============================================================================

async def generate_recommendations_from_insights(
    session: AsyncSession,
) -> List[Dict[str, Any]]:
    """
    Main entry point for recommendation generation.
    
    1. Load recent insights from database
    2. Generate recommendations from insights
    3. Return list of recommendation dicts (not yet saved)
    
    This function does NOT save to database - caller handles that.
    """
    logger.info("[RecommendationEngine] Starting recommendation generation from insights")
    
    # Load all relevant insight types
    insight_types = [
        AIRecommendationType.sales_insight,
        AIRecommendationType.demand_forecast,
        AIRecommendationType.yield_insight,
        AIRecommendationType.waste_alert,
    ]
    
    insights = await load_recent_insights(session, insight_types)
    logger.info(f"[RecommendationEngine] Loaded {len(insights)} recent insights")
    
    if not insights:
        logger.info("[RecommendationEngine] No insights found - cannot generate recommendations")
        return []
    
    all_recommendations = []
    
    # Generate each type of recommendation
    production_recs = await generate_production_recommendations(session, insights)
    all_recommendations.extend(production_recs)
    
    reorder_recs = await generate_reorder_recommendations(session, insights)
    all_recommendations.extend(reorder_recs)
    
    procurement_recs = await generate_procurement_recommendations(session, insights)
    all_recommendations.extend(procurement_recs)
    
    # Filter by minimum confidence
    filtered = [r for r in all_recommendations if r.get("confidence", 0) >= MIN_CONFIDENCE_FOR_RECOMMENDATION]
    
    logger.info(f"[RecommendationEngine] Generated {len(filtered)} recommendations (filtered from {len(all_recommendations)})")
    return filtered


async def run_recommendation_engine(
    session: AsyncSession,
) -> Dict[str, Any]:
    """
    Run the full recommendation engine.
    
    1. Generate recommendations from insights
    2. Deduplicate against existing recommendations (Phase 4.2)
    3. Save to database (same ai_recommendations table, different mode)
    4. Return summary
    
    Called by:
    - POST /api/ai/recommendations/run
    - Scheduled nightly job
    """
    logger.info("[RecommendationEngine] Running recommendation engine")
    
    results = {
        "started_at": datetime.utcnow().isoformat(),
        "recommendations_generated": 0,
        "duplicates_filtered": 0,
        "by_type": {},
    }
    
    try:
        # Generate recommendations
        recommendations = await generate_recommendations_from_insights(session)
        total_before_dedup = len(recommendations)
        
        # Deduplicate (Phase 4.2)
        unique_recommendations = await deduplicate_recommendations(session, recommendations)
        results["duplicates_filtered"] = total_before_dedup - len(unique_recommendations)
        
        # Save to database
        saved_count = 0
        for rec in unique_recommendations:
            db_rec = AIRecommendation(
                type=rec["type"],
                scope=AIRecommendationScope.admin,  # Always admin-only
                confidence=rec.get("confidence", 0.5),
                summary=rec["summary"],
                explanation=json.dumps(rec.get("explanation", [])),
                data_refs=json.dumps(rec.get("data_refs", {})),
                generated_by=AIGenerationMode.recommendation,  # Mark as recommendation
                status=AIRecommendationStatus.pending,  # Start as pending
                expires_at=datetime.utcnow() + timedelta(days=7),
            )
            session.add(db_rec)
            saved_count += 1
            
            # Count by type
            type_name = rec["type"].value if hasattr(rec["type"], "value") else str(rec["type"])
            results["by_type"][type_name] = results["by_type"].get(type_name, 0) + 1
        
        if saved_count > 0:
            await session.commit()
        
        results["recommendations_generated"] = saved_count
        results["status"] = "completed"
        results["completed_at"] = datetime.utcnow().isoformat()
        
        logger.info(f"[RecommendationEngine] Complete - generated {saved_count} recommendations ({results['duplicates_filtered']} duplicates filtered)")
        
    except Exception as e:
        logger.exception(f"[RecommendationEngine] Error: {e}")
        results["status"] = "error"
        results["error"] = str(e)
    
    return results
