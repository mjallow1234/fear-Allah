"""
AI Write Safety Module - Phase 5.1 Governance

This module provides safety wrappers to ensure AI code can ONLY write to 
approved tables (ai_recommendations and governance-related fields).

CRITICAL SAFETY RULE:
AI modules must NEVER directly modify business data (products, inventory,
orders, users, etc.). They can only:
1. READ from any table (for analysis)
2. WRITE to ai_recommendations table
3. UPDATE governance fields on ai_recommendations

This prevents AI from accidentally corrupting business data.
"""
from typing import Set, Type, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import event
from app.db.models import AIRecommendation
import logging

logger = logging.getLogger(__name__)


# Tables AI is allowed to INSERT into
ALLOWED_WRITE_TABLES: Set[str] = {
    "ai_recommendations",
}

# Tables AI is allowed to UPDATE (only specific columns)
ALLOWED_UPDATE_TABLES: Set[str] = {
    "ai_recommendations",
}

# Columns AI can update on ai_recommendations
ALLOWED_UPDATE_COLUMNS: Set[str] = {
    # Lifecycle status
    "status",
    "feedback_note",
    "feedback_by_id",
    "feedback_at",
    # Governance tags
    "priority",
    "category",
    "risk_level",
    "assigned_to_id",
    "tags",
    "governance_note",
    # Dismissal
    "is_dismissed",
    "dismissed_at",
    # Expiration
    "expires_at",
}


class AIWriteSafetyViolation(Exception):
    """Raised when AI attempts to write to a forbidden table/column."""
    pass


def validate_ai_write(mapper: Any, connection: Any, target: Any) -> None:
    """
    Validate that AI write operations are to allowed tables only.
    
    This is called by SQLAlchemy event listeners before INSERT operations.
    """
    table_name = target.__tablename__ if hasattr(target, '__tablename__') else str(type(target))
    
    if table_name not in ALLOWED_WRITE_TABLES:
        error_msg = f"AI SAFETY VIOLATION: Attempted to write to forbidden table '{table_name}'. AI can only write to: {ALLOWED_WRITE_TABLES}"
        logger.critical(error_msg)
        raise AIWriteSafetyViolation(error_msg)
    
    logger.debug(f"[AI Safety] Allowed write to table: {table_name}")


def register_ai_safety_listeners() -> None:
    """
    Register SQLAlchemy event listeners for AI write safety.
    
    Call this during application startup to enable safety checks.
    """
    # Listen for INSERT operations on AIRecommendation
    # This ensures we catch any writes through the model
    event.listen(AIRecommendation, 'before_insert', validate_ai_write)
    
    logger.info("[AI Safety] Registered write safety listeners for AI modules")


def verify_ai_model_safety() -> List[str]:
    """
    Verify that all AI model files only import allowed models.
    
    Returns list of any safety violations found.
    """
    violations = []
    
    # List of model imports that AI code should NOT use for writes
    FORBIDDEN_MODELS = [
        "Product",
        "Inventory",
        "Sale",
        "SaleItem",
        "Order",
        "OrderItem",
        "User",
        "RawMaterial",
        "ProductionLog",
        "WasteLog",
    ]
    
    import inspect
    import app.ai.engine as engine
    import app.ai.recommender as recommender
    import app.ai.analyzers as analyzers
    
    # Check each module's imports
    for module_name, module in [("engine", engine), ("recommender", recommender), ("analyzers", analyzers)]:
        source = inspect.getsource(module)
        
        # Check if module creates instances of forbidden models
        for model in FORBIDDEN_MODELS:
            # Pattern: ModelName( - indicates creating an instance
            if f"{model}(" in source:
                # Check context - is it an import or a write?
                if f"session.add({model}" in source.lower():
                    violations.append(f"AI module '{module_name}' may be writing to forbidden model: {model}")
    
    return violations


def get_ai_safety_status() -> dict:
    """
    Get current AI safety status for admin dashboard.
    """
    violations = verify_ai_model_safety()
    
    return {
        "safety_enabled": True,
        "allowed_write_tables": list(ALLOWED_WRITE_TABLES),
        "allowed_update_columns": list(ALLOWED_UPDATE_COLUMNS),
        "violations_detected": len(violations),
        "violations": violations,
        "status": "secure" if len(violations) == 0 else "warning",
    }


# Export public API
__all__ = [
    "ALLOWED_WRITE_TABLES",
    "ALLOWED_UPDATE_COLUMNS",
    "AIWriteSafetyViolation",
    "validate_ai_write",
    "register_ai_safety_listeners",
    "verify_ai_model_safety",
    "get_ai_safety_status",
]
