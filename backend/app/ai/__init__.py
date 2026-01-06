"""
AI Advisory Module

This package contains the AI advisory system for business intelligence.
AI observes → analyzes → recommends → explains
Humans approve → execute

Phase 9.1: Read Models (Insights)
- Sales velocity analysis
- Inventory coverage days
- Raw material burn rate
- Production yield averages
- Waste baselines

Output: Facts + Explanations (NO advice yet)

SAFETY: AI writes ONLY to ai_recommendations table.
All writes are validated by the safety module (Phase 5.1).
"""
from app.ai.engine import (
    # Analysis runners
    run_all_analysis,
    run_demand_forecast,
    run_production_advisor,
    run_waste_analysis,
    run_sales_intelligence,
    # Recommendation management
    get_recommendations,
    get_recommendation_count,
    dismiss_recommendation,
    clear_old_recommendations,
    # Exceptions
    AIEngineError,
    AIAnalysisError,
)

from app.ai.scheduler import (
    # Scheduler hooks (stubs)
    run_nightly_analysis,
    run_weekly_cleanup,
    setup_scheduler,
    shutdown_scheduler,
    get_scheduler_status,
)

from app.ai.analyzers import (
    # Individual analyzers
    analyze_sales_velocity,
    analyze_inventory_coverage,
    analyze_raw_material_burn_rate,
    analyze_production_yields,
    analyze_waste_baselines,
    run_all_analyzers,
)

from app.ai.recommender import (
    # Recommendation engine (Phase 9.2)
    generate_recommendations_from_insights,
    run_recommendation_engine,
)

from app.ai.safety import (
    # Write safety (Phase 5.1)
    AIWriteSafetyViolation,
    get_ai_safety_status,
    register_ai_safety_listeners,
    verify_ai_model_safety,
)

__all__ = [
    # Engine
    "run_all_analysis",
    "run_demand_forecast",
    "run_production_advisor",
    "run_waste_analysis",
    "run_sales_intelligence",
    "get_recommendations",
    "get_recommendation_count",
    "dismiss_recommendation",
    "clear_old_recommendations",
    "AIEngineError",
    "AIAnalysisError",
    # Scheduler
    "run_nightly_analysis",
    "run_weekly_cleanup",
    "setup_scheduler",
    "shutdown_scheduler",
    "get_scheduler_status",
    # Analyzers
    "analyze_sales_velocity",
    "analyze_inventory_coverage",
    "analyze_raw_material_burn_rate",
    "analyze_production_yields",
    "analyze_waste_baselines",
    "run_all_analyzers",
    # Recommender
    "generate_recommendations_from_insights",
    "run_recommendation_engine",
    # Safety (Phase 5.1)
    "AIWriteSafetyViolation",
    "get_ai_safety_status",
    "register_ai_safety_listeners",
    "verify_ai_model_safety",
]
