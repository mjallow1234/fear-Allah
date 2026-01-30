"""
Form Submission Service - Routes form submissions to backend services.

This is the mapping layer that connects dynamic forms to existing business logic.
Forms define data - this service routes that data to the right place.

Supported services:
- sales: Record sales
- orders: Create orders
- inventory: Manage inventory
- raw_materials: Raw material transactions
- production: Production batches
"""
import json
import logging
from typing import Optional, Tuple, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import Form, FormSubmission
from app.db.enums import FormCategory

logger = logging.getLogger(__name__)


class FormSubmissionService:
    """
    Routes form submissions to appropriate backend services.
    Uses field mapping to transform form data to service format.
    """
    
    # Service handlers registry
    _handlers = {}
    
    @classmethod
    def register_handler(cls, service_target: str, handler):
        """Register a handler function for a service target."""
        cls._handlers[service_target] = handler
    
    @classmethod
    async def submit(
        cls,
        db: AsyncSession,
        form: Form,
        data: dict,
        user_id: int,
        submission: Optional[FormSubmission] = None,
    ) -> Tuple[str, int, Optional[str]]:
        """
        Submit form data to the appropriate service.
        
        Returns: (status, result_id, error_message)
        - status: "processed" or "failed"
        - result_id: ID from the target service (e.g., sale_id, order_id)
        - error_message: Error message if failed
        """
        service_target = form.service_target
        
        if not service_target:
            # No service target - just record the submission
            return "processed", 0, None
        
        # Apply field mapping
        mapped_data = cls._apply_mapping(form, data)
        
        # Get handler
        handler = cls._handlers.get(service_target)
        if not handler:
            logger.warning(f"No handler registered for service: {service_target}")
            return "failed", 0, f"No handler for service: {service_target}"
        
        try:
            # Pass submission through to handlers so they can persist raw form payload if needed
            result_id = await handler(db, mapped_data, user_id, submission=submission)
            return "processed", result_id, None
        except ValueError as e:
            logger.error(f"Validation error in form submission: {e}")
            return "failed", 0, str(e)
        except Exception as e:
            logger.error(f"Error in form submission to {service_target}: {e}")
            return "failed", 0, str(e)
    
    @classmethod
    def _apply_mapping(cls, form: Form, data: dict) -> dict:
        """
        Apply field mapping to transform form data to service format.
        
        Mapping format:
        {
            "form_field_key": "service.field_name",
            "product_id": "inventory.product_id",
            "quantity": "sales.quantity"
        }
        
        If no mapping defined, data is passed through as-is.
        """
        if not form.field_mapping:
            return data
        
        try:
            mapping = json.loads(form.field_mapping)
        except (json.JSONDecodeError, TypeError):
            return data
        
        if not mapping:
            return data
        
        mapped = {}
        for form_key, target in mapping.items():
            if form_key in data:
                # Target can be "service.field" or just "field"
                if "." in target:
                    _, field_name = target.split(".", 1)
                else:
                    field_name = target
                mapped[field_name] = data[form_key]
        
        # Also include any fields not in mapping (passthrough)
        for key, value in data.items():
            if key not in mapping:
                mapped[key] = value
        
        return mapped
    
    @classmethod
    def validate_required_fields(cls, form: Form, data: dict) -> list:
        """
        Validate that all required fields are present.
        Returns list of missing field keys.
        """
        missing = []
        for field in form.fields:
            if field.required and field.key not in data:
                missing.append(field.key)
            elif field.required and data.get(field.key) in [None, "", []]:
                missing.append(field.key)
        return missing


# ============================================================================
# Service Handlers
# ============================================================================

async def handle_sales_submission(db: AsyncSession, data: dict, user_id: int, submission: Optional[FormSubmission] = None) -> int:
    """Handle form submission for sales service."""
    from app.services.sales import SalesService
    
    sale = await SalesService.record_sale(
        db=db,
        product_id=data.get("product_id"),
        quantity=data.get("quantity"),
        amount=data.get("amount"),
        channel=data.get("channel", "direct"),
        notes=data.get("notes"),
        recorded_by=user_id,
        # Optional fields from forms extension
        reference=data.get("reference"),
        customer_name=data.get("customer_name"),
        customer_phone=data.get("customer_phone"),
        discount=data.get("discount"),
        payment_method=data.get("payment_method"),
        sale_date=data.get("sale_date"),
        affiliate_code=data.get("affiliate_code"),
        affiliate_name=data.get("affiliate_name"),
        affiliate_source=data.get("affiliate_source"),
    )
    return sale.id


async def handle_orders_submission(db: AsyncSession, data: dict, user_id: int, submission: Optional[FormSubmission] = None) -> int:
    """Handle form submission for orders service.

    If a FormSubmission record is available, attach the full raw submission payload
    into the order metadata under `form_payload` without filtering or normalization.
    """
    from app.services.task_engine import create_order

    # Build metadata dict preserving any mapped metadata field
    meta = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}

    # Attach raw form submission payload and IDs when available (do not mutate submitted data)
    if submission is not None:
        try:
            form_payload = json.loads(submission.data) if isinstance(submission.data, str) else submission.data
        except Exception:
            form_payload = submission.data

        try:
            meta = dict(meta) if meta is not None else {}
            meta["form_payload"] = form_payload
            meta["form_submission_id"] = submission.id
            meta["form_id"] = submission.form_id
            meta["form_version"] = submission.form_version
        except Exception:
            # Best-effort: do not fail submission on meta attach
            logger.warning("[FormSubmission] Failed to attach form submission meta to order metadata")

    order = await create_order(
        session=db,
        order_type=data.get("order_type", "agent_restock"),
        items=json.dumps(data.get("items")) if data.get("items") else None,
        metadata=meta if meta else None,
        created_by_id=user_id,
        # Optional fields from forms extension
        reference=data.get("reference"),
        priority=data.get("priority"),
        requested_delivery_date=data.get("requested_delivery_date"),
        customer_name=data.get("customer_name"),
        customer_phone=data.get("customer_phone"),
        payment_method=data.get("payment_method"),
        internal_comment=data.get("internal_comment"),
    )
    return order.id


async def handle_inventory_submission(db: AsyncSession, data: dict, user_id: int, submission: Optional[FormSubmission] = None) -> int:
    """Handle form submission for inventory adjustments."""
    from app.services.inventory import InventoryService
    
    # Determine operation type
    operation = data.get("operation", "adjust")
    product_id = data.get("product_id")
    quantity = data.get("quantity", 0)
    reason = data.get("reason", "form_submission")
    notes = data.get("notes")
    
    if operation == "add":
        result = await InventoryService.add_stock(
            db=db,
            product_id=product_id,
            quantity=quantity,
            reason=reason,
            notes=notes,
            performed_by=user_id,
        )
    elif operation == "remove":
        result = await InventoryService.remove_stock(
            db=db,
            product_id=product_id,
            quantity=quantity,
            reason=reason,
            notes=notes,
            performed_by=user_id,
        )
    else:  # adjust
        result = await InventoryService.adjust_stock(
            db=db,
            product_id=product_id,
            new_quantity=quantity,
            reason=reason,
            notes=notes,
            performed_by=user_id,
        )
    
    return result.id if hasattr(result, 'id') else 0


async def handle_raw_materials_submission(db: AsyncSession, data: dict, user_id: int, submission: Optional[FormSubmission] = None) -> int:
    """Handle form submission for raw material transactions."""
    from app.db.models import RawMaterial, RawMaterialTransaction
    from sqlalchemy import select
    
    raw_material_id = data.get("raw_material_id")
    change = data.get("change", 0)
    reason = data.get("reason", "form_submission")
    notes = data.get("notes")
    
    # Get raw material
    result = await db.execute(select(RawMaterial).where(RawMaterial.id == raw_material_id))
    raw_material = result.scalar_one_or_none()
    
    if not raw_material:
        raise ValueError(f"Raw material {raw_material_id} not found")
    
    # Update stock
    raw_material.current_stock = (raw_material.current_stock or 0) + change
    
    # Create transaction record
    transaction = RawMaterialTransaction(
        raw_material_id=raw_material_id,
        change=change,
        reason=reason,
        notes=notes,
        performed_by_id=user_id,
    )
    db.add(transaction)
    await db.flush()
    
    return transaction.id


async def handle_production_submission(db: AsyncSession, data: dict, user_id: int, submission: Optional[FormSubmission] = None) -> int:
    """Handle form submission for production batches."""
    from app.db.models import ProductionBatch, BatchInput, BatchOutput
    
    batch = ProductionBatch(
        batch_reference=data.get("batch_reference"),
        status="pending",
        notes=data.get("notes"),
        created_by_id=user_id,
    )
    db.add(batch)
    await db.flush()
    
    # Add inputs
    inputs = data.get("inputs", [])
    for inp in inputs:
        batch_input = BatchInput(
            batch_id=batch.id,
            raw_material_id=inp.get("raw_material_id"),
            quantity_used=inp.get("quantity"),
            unit_cost=inp.get("unit_cost"),
        )
        db.add(batch_input)
    
    # Add outputs (if completing batch)
    outputs = data.get("outputs", [])
    for out in outputs:
        batch_output = BatchOutput(
            batch_id=batch.id,
            product_id=out.get("product_id"),
            quantity_produced=out.get("quantity"),
        )
        db.add(batch_output)
    
    await db.flush()
    return batch.id


# Register handlers
FormSubmissionService.register_handler("sales", handle_sales_submission)
FormSubmissionService.register_handler("orders", handle_orders_submission)
FormSubmissionService.register_handler("inventory", handle_inventory_submission)
FormSubmissionService.register_handler("raw_materials", handle_raw_materials_submission)
FormSubmissionService.register_handler("production", handle_production_submission)
