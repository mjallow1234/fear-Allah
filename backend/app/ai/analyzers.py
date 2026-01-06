"""
AI Read Models / Analyzers (Phase 9.1)

Read-only analyzers that compute business intelligence metrics.
These produce INSIGHTS (facts + explanations), NOT recommendations.

Output Format:
{
    "type": "sales_insight" | "yield_insight" | ...,
    "summary": "Factual statement about what happened",
    "explanation": ["Supporting fact 1", "Supporting fact 2"],
    "confidence": 0.0 - 1.0,
    "data_refs": {"product_ids": [...], "date_range": "..."}
}

❌ No "produce X"
❌ No "order Y" 
❌ No "reduce waste"
✅ Just facts + explanations

SAFETY GUARANTEE:
- These functions ONLY READ from business tables
- They WRITE ONLY to ai_recommendations table via the engine
"""
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal
import logging
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, case
from sqlalchemy.orm import selectinload

from app.db.models import (
    Sale, Inventory, RawMaterial, RawMaterialTransaction,
    ProcessingBatch, ProcessingRecipe, AIRecommendation
)
from app.db.enums import (
    AIRecommendationType, AIRecommendationScope, AIGenerationMode, ProductType
)

logger = logging.getLogger(__name__)


# ============================================================================
# Helper Functions
# ============================================================================

def calculate_confidence(sample_size: int, min_samples: int = 7, max_samples: int = 30) -> float:
    """
    Calculate confidence based on sample size.
    More data = higher confidence.
    """
    if sample_size < min_samples:
        return 0.3 + (sample_size / min_samples) * 0.3  # 0.3 - 0.6
    elif sample_size < max_samples:
        return 0.6 + ((sample_size - min_samples) / (max_samples - min_samples)) * 0.3  # 0.6 - 0.9
    else:
        return 0.9  # Max confidence


def format_percent_change(old_value: float, new_value: float) -> str:
    """Format a percent change for human reading."""
    if old_value == 0:
        return "∞% increase" if new_value > 0 else "no change"
    change = ((new_value - old_value) / old_value) * 100
    if change > 0:
        return f"{change:.0f}% increase"
    elif change < 0:
        return f"{abs(change):.0f}% decrease"
    else:
        return "no change"


# ============================================================================
# Sales Velocity Analyzer
# ============================================================================

async def analyze_sales_velocity(
    session: AsyncSession,
    lookback_days: int = 14,
    comparison_days: int = 14,
) -> List[Dict[str, Any]]:
    """
    Analyze sales velocity (units sold per day) for each product.
    
    Compares:
    - Recent period (last `lookback_days` days)
    - Previous period (`comparison_days` before that)
    
    Returns insights about significant changes in sales patterns.
    """
    logger.info(f"[Analyzer] Analyzing sales velocity (lookback={lookback_days}d, compare={comparison_days}d)")
    
    now = datetime.utcnow()
    recent_start = now - timedelta(days=lookback_days)
    previous_start = recent_start - timedelta(days=comparison_days)
    
    insights = []
    
    # Get recent sales grouped by product
    recent_sales_query = (
        select(
            Sale.product_id,
            func.count(Sale.id).label('sale_count'),
            func.sum(Sale.quantity).label('total_qty')
        )
        .where(Sale.created_at >= recent_start)
        .group_by(Sale.product_id)
    )
    recent_result = await session.execute(recent_sales_query)
    recent_sales = {row.product_id: {'count': row.sale_count, 'qty': row.total_qty or 0} 
                    for row in recent_result.all()}
    
    # Get previous period sales
    previous_sales_query = (
        select(
            Sale.product_id,
            func.count(Sale.id).label('sale_count'),
            func.sum(Sale.quantity).label('total_qty')
        )
        .where(and_(
            Sale.created_at >= previous_start,
            Sale.created_at < recent_start
        ))
        .group_by(Sale.product_id)
    )
    previous_result = await session.execute(previous_sales_query)
    previous_sales = {row.product_id: {'count': row.sale_count, 'qty': row.total_qty or 0} 
                      for row in previous_result.all()}
    
    # Get product names
    all_product_ids = set(recent_sales.keys()) | set(previous_sales.keys())
    if not all_product_ids:
        logger.info("[Analyzer] No sales data found for velocity analysis")
        return insights
    
    inventory_query = select(Inventory).where(Inventory.product_id.in_(all_product_ids))
    inv_result = await session.execute(inventory_query)
    products = {inv.product_id: inv for inv in inv_result.scalars().all()}
    
    # Analyze each product
    for product_id in all_product_ids:
        recent = recent_sales.get(product_id, {'count': 0, 'qty': 0})
        previous = previous_sales.get(product_id, {'count': 0, 'qty': 0})
        product = products.get(product_id)
        product_name = product.product_name if product else f"Product {product_id}"
        
        # Calculate daily averages
        recent_daily_avg = recent['qty'] / lookback_days if lookback_days > 0 else 0
        previous_daily_avg = previous['qty'] / comparison_days if comparison_days > 0 else 0
        
        # Skip if no meaningful data
        if recent['qty'] == 0 and previous['qty'] == 0:
            continue
        
        # Calculate change
        if previous_daily_avg > 0:
            pct_change = ((recent_daily_avg - previous_daily_avg) / previous_daily_avg) * 100
        else:
            pct_change = 100 if recent_daily_avg > 0 else 0
        
        # Only report significant changes (>10% change)
        if abs(pct_change) < 10:
            continue
        
        # Build insight
        if pct_change > 0:
            summary = f"{product_name} sales increased {pct_change:.0f}% this period"
        else:
            summary = f"{product_name} sales decreased {abs(pct_change):.0f}% this period"
        
        explanation = [
            f"{lookback_days}-day average: {recent_daily_avg:.1f} units/day",
            f"Previous {comparison_days}-day average: {previous_daily_avg:.1f} units/day",
            f"Total recent sales: {recent['qty']} units across {recent['count']} transactions",
        ]
        
        # Add current stock context if available
        if product and product.total_stock is not None:
            days_of_stock = product.total_stock / recent_daily_avg if recent_daily_avg > 0 else float('inf')
            if days_of_stock < float('inf'):
                explanation.append(f"Current stock: {product.total_stock} units ({days_of_stock:.0f} days at current rate)")
        
        sample_size = recent['count'] + previous['count']
        confidence = calculate_confidence(sample_size)
        
        insights.append({
            "type": AIRecommendationType.sales_insight,
            "summary": summary,
            "explanation": explanation,
            "confidence": confidence,
            "data_refs": {
                "product_id": product_id,
                "product_name": product_name,
                "recent_period_days": lookback_days,
                "comparison_period_days": comparison_days,
                "recent_qty": recent['qty'],
                "previous_qty": previous['qty'],
            }
        })
    
    logger.info(f"[Analyzer] Generated {len(insights)} sales velocity insights")
    return insights


# ============================================================================
# Inventory Coverage Analyzer
# ============================================================================

async def analyze_inventory_coverage(
    session: AsyncSession,
    lookback_days: int = 14,
) -> List[Dict[str, Any]]:
    """
    Calculate inventory coverage days for each finished good.
    
    Coverage Days = Current Stock / Average Daily Sales
    
    Reports:
    - Products with low coverage (<7 days)
    - Products with high coverage (>30 days, potential overstock)
    """
    logger.info(f"[Analyzer] Analyzing inventory coverage (lookback={lookback_days}d)")
    
    now = datetime.utcnow()
    lookback_start = now - timedelta(days=lookback_days)
    
    insights = []
    
    # Get all finished goods
    inventory_query = (
        select(Inventory)
        .where(Inventory.product_type == ProductType.finished_good)
    )
    inv_result = await session.execute(inventory_query)
    finished_goods = list(inv_result.scalars().all())
    
    if not finished_goods:
        logger.info("[Analyzer] No finished goods found for coverage analysis")
        return insights
    
    # Get sales velocity for each product
    for product in finished_goods:
        sales_query = (
            select(func.sum(Sale.quantity).label('total_qty'))
            .where(and_(
                Sale.product_id == product.product_id,
                Sale.created_at >= lookback_start
            ))
        )
        sales_result = await session.execute(sales_query)
        total_sales = sales_result.scalar() or 0
        
        daily_avg = total_sales / lookback_days if lookback_days > 0 else 0
        
        # Calculate coverage days
        if daily_avg > 0:
            coverage_days = product.total_stock / daily_avg
        else:
            coverage_days = float('inf') if product.total_stock > 0 else 0
        
        product_name = product.product_name or f"Product {product.product_id}"
        
        # Generate insight based on coverage
        if coverage_days == float('inf') and product.total_stock > 0:
            # No sales but have stock
            summary = f"{product_name}: No recent sales, {product.total_stock} units in stock"
            explanation = [
                f"Current stock: {product.total_stock} units",
                f"No sales recorded in the past {lookback_days} days",
                "Coverage days: Unlimited (no demand)"
            ]
            confidence = 0.5  # Lower confidence for no-sale scenario
        elif coverage_days < 7:
            # Low coverage - critical
            summary = f"{product_name}: Only {coverage_days:.0f} days of stock remaining"
            explanation = [
                f"Current stock: {product.total_stock} units",
                f"Average daily sales: {daily_avg:.1f} units/day",
                f"At current rate, stock depletes in ~{coverage_days:.0f} days"
            ]
            confidence = calculate_confidence(int(daily_avg * lookback_days))
        elif coverage_days > 30 and product.total_stock > 0:
            # High coverage - potential overstock
            summary = f"{product_name}: {coverage_days:.0f} days of stock (potential overstock)"
            explanation = [
                f"Current stock: {product.total_stock} units",
                f"Average daily sales: {daily_avg:.1f} units/day",
                f"Stock covers ~{coverage_days:.0f} days of demand"
            ]
            confidence = calculate_confidence(int(daily_avg * lookback_days))
        else:
            # Normal coverage - skip
            continue
        
        insights.append({
            "type": AIRecommendationType.demand_forecast,  # Using demand_forecast for coverage insights
            "summary": summary,
            "explanation": explanation,
            "confidence": confidence,
            "data_refs": {
                "product_id": product.product_id,
                "product_name": product_name,
                "current_stock": product.total_stock,
                "daily_average_sales": round(daily_avg, 2),
                "coverage_days": round(coverage_days, 1) if coverage_days != float('inf') else None,
            }
        })
    
    logger.info(f"[Analyzer] Generated {len(insights)} inventory coverage insights")
    return insights


# ============================================================================
# Raw Material Burn Rate Analyzer
# ============================================================================

async def analyze_raw_material_burn_rate(
    session: AsyncSession,
    lookback_days: int = 14,
) -> List[Dict[str, Any]]:
    """
    Calculate raw material consumption rate (burn rate).
    
    Burn Rate = Raw material consumed / days
    Coverage = Current stock / burn rate
    
    Reports:
    - Materials being consumed faster than usual
    - Materials with low coverage (<7 days)
    """
    logger.info(f"[Analyzer] Analyzing raw material burn rate (lookback={lookback_days}d)")
    
    now = datetime.utcnow()
    lookback_start = now - timedelta(days=lookback_days)
    
    insights = []
    
    # Get all raw materials
    rm_query = select(RawMaterial)
    rm_result = await session.execute(rm_query)
    raw_materials = list(rm_result.scalars().all())
    
    if not raw_materials:
        logger.info("[Analyzer] No raw materials found for burn rate analysis")
        return insights
    
    for material in raw_materials:
        # Get consumption (negative changes from processing)
        consumption_query = (
            select(func.sum(func.abs(RawMaterialTransaction.change)).label('total_consumed'))
            .where(and_(
                RawMaterialTransaction.raw_material_id == material.id,
                RawMaterialTransaction.change < 0,  # Consumption is negative
                RawMaterialTransaction.created_at >= lookback_start
            ))
        )
        consumption_result = await session.execute(consumption_query)
        total_consumed = consumption_result.scalar() or 0
        
        # Calculate daily burn rate
        daily_burn = total_consumed / lookback_days if lookback_days > 0 else 0
        
        if daily_burn == 0:
            continue  # Skip materials not being consumed
        
        # Calculate coverage
        coverage_days = material.current_stock / daily_burn if daily_burn > 0 else float('inf')
        
        # Generate insight for low coverage
        if coverage_days < 14:  # Alert if <14 days of supply
            if coverage_days < 7:
                summary = f"{material.name}: Critical - only {coverage_days:.0f} days of supply"
            else:
                summary = f"{material.name}: {coverage_days:.0f} days of supply remaining"
            
            explanation = [
                f"Current stock: {material.current_stock} {material.unit}",
                f"Average daily consumption: {daily_burn:.1f} {material.unit}/day",
                f"Consumed {total_consumed:.0f} {material.unit} in past {lookback_days} days"
            ]
            
            if material.min_stock_level and material.current_stock <= material.min_stock_level:
                explanation.append(f"⚠️ Stock is at or below minimum level ({material.min_stock_level} {material.unit})")
            
            insights.append({
                "type": AIRecommendationType.demand_forecast,
                "summary": summary,
                "explanation": explanation,
                "confidence": calculate_confidence(int(total_consumed)),
                "data_refs": {
                    "raw_material_id": material.id,
                    "raw_material_name": material.name,
                    "current_stock": material.current_stock,
                    "unit": material.unit,
                    "daily_burn_rate": round(daily_burn, 2),
                    "coverage_days": round(coverage_days, 1),
                }
            })
    
    logger.info(f"[Analyzer] Generated {len(insights)} raw material burn rate insights")
    return insights


# ============================================================================
# Production Yield Analyzer
# ============================================================================

async def analyze_production_yields(
    session: AsyncSession,
    lookback_days: int = 30,
) -> List[Dict[str, Any]]:
    """
    Analyze production yield efficiency across batches.
    
    Calculates:
    - Average yield efficiency per product
    - Trends (improving/declining)
    - Anomalous batches
    """
    logger.info(f"[Analyzer] Analyzing production yields (lookback={lookback_days}d)")
    
    now = datetime.utcnow()
    lookback_start = now - timedelta(days=lookback_days)
    
    insights = []
    
    # Get completed batches with yield data
    batch_query = (
        select(ProcessingBatch)
        .options(selectinload(ProcessingBatch.finished_product))
        .where(and_(
            ProcessingBatch.status == "completed",
            ProcessingBatch.created_at >= lookback_start,
            ProcessingBatch.yield_efficiency.isnot(None)
        ))
        .order_by(ProcessingBatch.finished_product_id, ProcessingBatch.created_at)
    )
    batch_result = await session.execute(batch_query)
    batches = list(batch_result.scalars().all())
    
    if not batches:
        logger.info("[Analyzer] No production batches found for yield analysis")
        return insights
    
    # Group by product
    product_batches: Dict[int, List[ProcessingBatch]] = {}
    for batch in batches:
        pid = batch.finished_product_id
        if pid not in product_batches:
            product_batches[pid] = []
        product_batches[pid].append(batch)
    
    for product_id, prod_batches in product_batches.items():
        if len(prod_batches) < 2:
            continue  # Need at least 2 batches for analysis
        
        product = prod_batches[0].finished_product
        product_name = product.product_name if product else f"Product {product_id}"
        
        # Calculate average yield
        yields = [b.yield_efficiency for b in prod_batches if b.yield_efficiency is not None]
        avg_yield = sum(yields) / len(yields) if yields else 0
        
        # Calculate trend (first half vs second half)
        mid = len(yields) // 2
        first_half_avg = sum(yields[:mid]) / mid if mid > 0 else 0
        second_half_avg = sum(yields[mid:]) / (len(yields) - mid) if len(yields) > mid else 0
        
        # Build insight
        if avg_yield < 80:
            summary = f"{product_name}: Average yield efficiency is {avg_yield:.0f}% (below target)"
        elif avg_yield > 95:
            summary = f"{product_name}: Excellent yield efficiency at {avg_yield:.0f}%"
        else:
            summary = f"{product_name}: Average yield efficiency is {avg_yield:.0f}%"
        
        explanation = [
            f"Analyzed {len(prod_batches)} production batches",
            f"Average yield: {avg_yield:.1f}%",
            f"Range: {min(yields):.0f}% - {max(yields):.0f}%",
        ]
        
        # Add trend insight
        if mid > 0 and first_half_avg > 0:
            trend_change = second_half_avg - first_half_avg
            if trend_change > 5:
                explanation.append(f"📈 Yield improving: {first_half_avg:.0f}% → {second_half_avg:.0f}%")
            elif trend_change < -5:
                explanation.append(f"📉 Yield declining: {first_half_avg:.0f}% → {second_half_avg:.0f}%")
        
        # Check for anomalies (batches with yield <70% or >100%)
        anomalies = [b for b in prod_batches if b.yield_efficiency and (b.yield_efficiency < 70 or b.yield_efficiency > 100)]
        if anomalies:
            explanation.append(f"⚠️ {len(anomalies)} batch(es) with unusual yield")
        
        insights.append({
            "type": AIRecommendationType.yield_insight,
            "summary": summary,
            "explanation": explanation,
            "confidence": calculate_confidence(len(prod_batches), min_samples=3, max_samples=20),
            "data_refs": {
                "product_id": product_id,
                "product_name": product_name,
                "batch_count": len(prod_batches),
                "average_yield": round(avg_yield, 1),
                "yield_range": {"min": min(yields), "max": max(yields)},
            }
        })
    
    logger.info(f"[Analyzer] Generated {len(insights)} production yield insights")
    return insights


# ============================================================================
# Waste Baseline Analyzer
# ============================================================================

async def analyze_waste_baselines(
    session: AsyncSession,
    lookback_days: int = 30,
) -> List[Dict[str, Any]]:
    """
    Establish waste baselines and detect anomalies.
    
    Calculates:
    - Average waste per product
    - Recent waste vs baseline
    - Anomalous spikes
    """
    logger.info(f"[Analyzer] Analyzing waste baselines (lookback={lookback_days}d)")
    
    now = datetime.utcnow()
    lookback_start = now - timedelta(days=lookback_days)
    recent_start = now - timedelta(days=7)  # Last 7 days for recent comparison
    
    insights = []
    
    # Get batches with waste data
    batch_query = (
        select(ProcessingBatch)
        .options(selectinload(ProcessingBatch.finished_product))
        .where(and_(
            ProcessingBatch.status == "completed",
            ProcessingBatch.created_at >= lookback_start,
            ProcessingBatch.actual_waste_quantity.isnot(None),
            ProcessingBatch.actual_waste_quantity > 0
        ))
        .order_by(ProcessingBatch.finished_product_id, ProcessingBatch.created_at)
    )
    batch_result = await session.execute(batch_query)
    batches = list(batch_result.scalars().all())
    
    if not batches:
        logger.info("[Analyzer] No batches with waste data found")
        return insights
    
    # Group by product
    product_batches: Dict[int, List[ProcessingBatch]] = {}
    for batch in batches:
        pid = batch.finished_product_id
        if pid not in product_batches:
            product_batches[pid] = []
        product_batches[pid].append(batch)
    
    for product_id, prod_batches in product_batches.items():
        if len(prod_batches) < 2:
            continue
        
        product = prod_batches[0].finished_product
        product_name = product.product_name if product else f"Product {product_id}"
        
        # Calculate baseline (all batches)
        waste_values = [b.actual_waste_quantity for b in prod_batches if b.actual_waste_quantity]
        avg_waste = sum(waste_values) / len(waste_values) if waste_values else 0
        
        # Calculate total waste
        total_waste = sum(waste_values)
        
        # Get recent batches
        recent_batches = [b for b in prod_batches if b.created_at >= recent_start]
        recent_waste = [b.actual_waste_quantity for b in recent_batches if b.actual_waste_quantity]
        recent_avg = sum(recent_waste) / len(recent_waste) if recent_waste else 0
        
        # Check for waste spike
        if avg_waste > 0:
            waste_change_pct = ((recent_avg - avg_waste) / avg_waste) * 100
        else:
            waste_change_pct = 0
        
        # Build insight
        if waste_change_pct > 20 and len(recent_batches) >= 2:
            summary = f"{product_name}: Waste increased {waste_change_pct:.0f}% vs baseline"
            explanation = [
                f"Baseline average waste: {avg_waste:.1f} units/batch",
                f"Recent average waste: {recent_avg:.1f} units/batch",
                f"Based on {len(recent_batches)} recent batches vs {len(prod_batches)} total",
            ]
            insights.append({
                "type": AIRecommendationType.waste_alert,
                "summary": summary,
                "explanation": explanation,
                "confidence": calculate_confidence(len(prod_batches)),
                "data_refs": {
                    "product_id": product_id,
                    "product_name": product_name,
                    "baseline_avg_waste": round(avg_waste, 1),
                    "recent_avg_waste": round(recent_avg, 1),
                    "waste_change_pct": round(waste_change_pct, 1),
                }
            })
        else:
            # Just report baseline
            summary = f"{product_name}: Total waste {total_waste:.0f} units (avg {avg_waste:.1f}/batch)"
            explanation = [
                f"Analyzed {len(prod_batches)} production batches",
                f"Total waste: {total_waste:.0f} units",
                f"Average waste per batch: {avg_waste:.1f} units",
            ]
            
            # Add waste notes if any patterns
            waste_notes = [b.waste_notes for b in prod_batches if b.waste_notes]
            if waste_notes:
                explanation.append(f"Recorded {len(waste_notes)} waste note(s)")
            
            insights.append({
                "type": AIRecommendationType.waste_alert,
                "summary": summary,
                "explanation": explanation,
                "confidence": calculate_confidence(len(prod_batches)),
                "data_refs": {
                    "product_id": product_id,
                    "product_name": product_name,
                    "total_waste": total_waste,
                    "average_waste": round(avg_waste, 1),
                    "batch_count": len(prod_batches),
                }
            })
    
    logger.info(f"[Analyzer] Generated {len(insights)} waste baseline insights")
    return insights


# ============================================================================
# Master Analysis Function
# ============================================================================

async def run_all_analyzers(
    session: AsyncSession,
    mode: AIGenerationMode = AIGenerationMode.auto,
) -> List[Dict[str, Any]]:
    """
    Run all analyzers and return combined insights.
    
    This is called by the engine to gather all read-only analytics.
    """
    logger.info(f"[Analyzers] Running all analyzers (mode={mode.value})")
    
    all_insights = []
    
    # Sales velocity
    try:
        velocity_insights = await analyze_sales_velocity(session)
        all_insights.extend(velocity_insights)
    except Exception as e:
        logger.error(f"[Analyzers] Sales velocity analysis failed: {e}")
    
    # Inventory coverage
    try:
        coverage_insights = await analyze_inventory_coverage(session)
        all_insights.extend(coverage_insights)
    except Exception as e:
        logger.error(f"[Analyzers] Inventory coverage analysis failed: {e}")
    
    # Raw material burn rate
    try:
        burn_insights = await analyze_raw_material_burn_rate(session)
        all_insights.extend(burn_insights)
    except Exception as e:
        logger.error(f"[Analyzers] Raw material burn rate analysis failed: {e}")
    
    # Production yields
    try:
        yield_insights = await analyze_production_yields(session)
        all_insights.extend(yield_insights)
    except Exception as e:
        logger.error(f"[Analyzers] Production yield analysis failed: {e}")
    
    # Waste baselines
    try:
        waste_insights = await analyze_waste_baselines(session)
        all_insights.extend(waste_insights)
    except Exception as e:
        logger.error(f"[Analyzers] Waste baseline analysis failed: {e}")
    
    logger.info(f"[Analyzers] Total insights generated: {len(all_insights)}")
    return all_insights
