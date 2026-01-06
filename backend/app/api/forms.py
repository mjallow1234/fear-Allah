"""
Form Builder API - Dynamic Forms System (Phase 8)

Provides:
- Admin CRUD for forms and fields
- Public form definition fetch
- Form submission with service routing
- Version management

Forms define data structure - not business logic.
Business logic stays in services (sales, orders, inventory).
"""
import json
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.db.models import Form, FormField, FormVersion, FormSubmission, User
from app.db.enums import FormFieldType, FormCategory, UserRole
from app.core.security import get_current_user, require_admin


router = APIRouter(prefix="/forms", tags=["Forms"])


# ============================================================================
# Pydantic Schemas
# ============================================================================

class FormFieldCreate(BaseModel):
    key: str = Field(..., min_length=1, max_length=100)
    label: str = Field(..., min_length=1, max_length=255)
    field_type: FormFieldType
    placeholder: Optional[str] = None
    help_text: Optional[str] = None
    required: bool = False
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None
    options: Optional[List[dict]] = None  # [{value, label}]
    options_source: Optional[str] = None
    default_value: Optional[str] = None
    role_visibility: Optional[List[str]] = None
    conditional_visibility: Optional[dict] = None
    order_index: int = 0
    field_group: Optional[str] = None


class FormFieldUpdate(BaseModel):
    key: Optional[str] = None
    label: Optional[str] = None
    field_type: Optional[FormFieldType] = None
    placeholder: Optional[str] = None
    help_text: Optional[str] = None
    required: Optional[bool] = None
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None
    options: Optional[List[dict]] = None
    options_source: Optional[str] = None
    default_value: Optional[str] = None
    role_visibility: Optional[List[str]] = None
    conditional_visibility: Optional[dict] = None
    order_index: Optional[int] = None
    field_group: Optional[str] = None


class FormFieldResponse(BaseModel):
    id: int
    key: str
    label: str
    field_type: str
    placeholder: Optional[str]
    help_text: Optional[str]
    required: bool
    min_value: Optional[int]
    max_value: Optional[int]
    min_length: Optional[int]
    max_length: Optional[int]
    pattern: Optional[str]
    options: Optional[List[dict]]
    options_source: Optional[str]
    default_value: Optional[str]
    role_visibility: Optional[List[str]]
    conditional_visibility: Optional[dict]
    order_index: int
    field_group: Optional[str]

    class Config:
        from_attributes = True


class FormCreate(BaseModel):
    slug: str = Field(..., min_length=1, max_length=100, pattern=r'^[a-z0-9_]+$')
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    category: FormCategory
    allowed_roles: Optional[List[str]] = None
    service_target: Optional[str] = None
    field_mapping: Optional[dict] = None
    is_active: bool = True


class FormUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[FormCategory] = None
    allowed_roles: Optional[List[str]] = None
    service_target: Optional[str] = None
    field_mapping: Optional[dict] = None
    is_active: Optional[bool] = None


class FormResponse(BaseModel):
    id: int
    slug: str
    name: str
    description: Optional[str]
    category: str
    allowed_roles: Optional[List[str]]
    service_target: Optional[str]
    field_mapping: Optional[dict]
    is_active: bool
    current_version: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    fields: List[FormFieldResponse] = []

    class Config:
        from_attributes = True


class FormListResponse(BaseModel):
    id: int
    slug: str
    name: str
    category: str
    is_active: bool
    field_count: int
    current_version: int

    class Config:
        from_attributes = True


class FormVersionResponse(BaseModel):
    id: int
    version: int
    change_notes: Optional[str]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class FormSubmissionCreate(BaseModel):
    data: dict = Field(..., description="Form field values")


class FormSubmissionResponse(BaseModel):
    id: int
    form_id: int
    form_version: int
    status: str
    result_id: Optional[int]
    result_type: Optional[str]
    error_message: Optional[str]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


# ============================================================================
# Helper Functions
# ============================================================================

def _parse_json_field(value: Optional[str]) -> Optional[any]:
    """Parse JSON string field, return None if empty or invalid."""
    if not value:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


def _serialize_json_field(value: Optional[any]) -> Optional[str]:
    """Serialize value to JSON string."""
    if value is None:
        return None
    return json.dumps(value)


def _field_to_response(field: FormField) -> FormFieldResponse:
    """Convert FormField model to response schema."""
    return FormFieldResponse(
        id=field.id,
        key=field.key,
        label=field.label,
        field_type=field.field_type.value if hasattr(field.field_type, 'value') else field.field_type,
        placeholder=field.placeholder,
        help_text=field.help_text,
        required=field.required,
        min_value=field.min_value,
        max_value=field.max_value,
        min_length=field.min_length,
        max_length=field.max_length,
        pattern=field.pattern,
        options=_parse_json_field(field.options),
        options_source=field.options_source,
        default_value=field.default_value,
        role_visibility=_parse_json_field(field.role_visibility),
        conditional_visibility=_parse_json_field(field.conditional_visibility),
        order_index=field.order_index,
        field_group=field.field_group,
    )


def _form_to_response(form: Form, include_fields: bool = True) -> FormResponse:
    """Convert Form model to response schema."""
    fields = []
    if include_fields and form.fields:
        fields = [_field_to_response(f) for f in sorted(form.fields, key=lambda x: x.order_index)]
    
    return FormResponse(
        id=form.id,
        slug=form.slug,
        name=form.name,
        description=form.description,
        category=form.category.value if hasattr(form.category, 'value') else form.category,
        allowed_roles=_parse_json_field(form.allowed_roles),
        service_target=form.service_target,
        field_mapping=_parse_json_field(form.field_mapping),
        is_active=form.is_active,
        current_version=form.current_version or 1,
        created_at=form.created_at,
        updated_at=form.updated_at,
        fields=fields,
    )


async def _create_version_snapshot(db: AsyncSession, form: Form, user_id: int, change_notes: str = None):
    """Create a version snapshot of the current form state."""
    # Build snapshot
    snapshot = {
        "slug": form.slug,
        "name": form.name,
        "description": form.description,
        "category": form.category.value if hasattr(form.category, 'value') else form.category,
        "allowed_roles": _parse_json_field(form.allowed_roles),
        "service_target": form.service_target,
        "field_mapping": _parse_json_field(form.field_mapping),
        "is_active": form.is_active,
        "fields": []
    }
    
    for field in form.fields:
        snapshot["fields"].append({
            "key": field.key,
            "label": field.label,
            "field_type": field.field_type.value if hasattr(field.field_type, 'value') else field.field_type,
            "placeholder": field.placeholder,
            "help_text": field.help_text,
            "required": field.required,
            "min_value": field.min_value,
            "max_value": field.max_value,
            "min_length": field.min_length,
            "max_length": field.max_length,
            "pattern": field.pattern,
            "options": _parse_json_field(field.options),
            "options_source": field.options_source,
            "default_value": field.default_value,
            "role_visibility": _parse_json_field(field.role_visibility),
            "conditional_visibility": _parse_json_field(field.conditional_visibility),
            "order_index": field.order_index,
            "field_group": field.field_group,
        })
    
    version = FormVersion(
        form_id=form.id,
        version=form.current_version,
        snapshot=json.dumps(snapshot),
        change_notes=change_notes,
        created_by_id=user_id,
    )
    db.add(version)


def _check_role_access(user_role: str, allowed_roles: List[str]) -> bool:
    """Check if user's role is in the allowed roles list."""
    if not allowed_roles:
        return True  # No restrictions
    
    # Admin always has access
    if user_role in ['system_admin', 'admin']:
        return True
    
    return user_role in allowed_roles


def _filter_fields_by_role(fields: List[FormFieldResponse], user_role: str) -> List[FormFieldResponse]:
    """Filter fields based on user's role visibility."""
    filtered = []
    for field in fields:
        # If no role visibility set, field is visible to all
        if not field.role_visibility:
            filtered.append(field)
            continue
        
        # Admin sees all
        if user_role in ['system_admin', 'admin']:
            filtered.append(field)
            continue
        
        # Check if user's role is in visibility list
        if user_role in field.role_visibility:
            filtered.append(field)
    
    return filtered


# ============================================================================
# Admin CRUD Endpoints
# ============================================================================

@router.post("/admin", response_model=FormResponse, status_code=status.HTTP_201_CREATED)
async def create_form(
    payload: FormCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Create a new form definition.
    Admin only.
    """
    await require_admin(db, current_user)
    
    # Check slug uniqueness
    existing = await db.execute(select(Form).where(Form.slug == payload.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Form with slug '{payload.slug}' already exists")
    
    form = Form(
        slug=payload.slug,
        name=payload.name,
        description=payload.description,
        category=payload.category,
        allowed_roles=_serialize_json_field(payload.allowed_roles),
        service_target=payload.service_target,
        field_mapping=_serialize_json_field(payload.field_mapping),
        is_active=payload.is_active,
        current_version=1,
        created_by_id=current_user["user_id"],
    )
    db.add(form)
    await db.flush()
    
    # Create initial version
    await _create_version_snapshot(db, form, current_user["user_id"], "Initial creation")
    
    await db.commit()
    await db.refresh(form)
    
    return _form_to_response(form)


@router.get("/admin", response_model=List[FormListResponse])
async def list_forms_admin(
    category: Optional[FormCategory] = None,
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    List all forms with basic info.
    Admin only.
    """
    await require_admin(db, current_user)
    
    query = select(Form).options(selectinload(Form.fields))
    
    if category:
        query = query.where(Form.category == category)
    if is_active is not None:
        query = query.where(Form.is_active == is_active)
    
    query = query.order_by(Form.category, Form.name)
    
    result = await db.execute(query)
    forms = result.scalars().all()
    
    return [
        FormListResponse(
            id=f.id,
            slug=f.slug,
            name=f.name,
            category=f.category.value if hasattr(f.category, 'value') else f.category,
            is_active=f.is_active,
            field_count=len(f.fields) if f.fields else 0,
            current_version=f.current_version or 1,
        )
        for f in forms
    ]


# ============================================================================
# Seed Forms Endpoint (must be before /admin/{form_id} routes)
# ============================================================================

# Default form definitions for seeding
SEED_FORMS = [
    {
        "name": "Sales Form",
        "slug": "sales",
        "category": "sale",
        "description": "Record sales transactions",
        "service_target": "sales.create_sale",
        "fields": [
            {"key": "product_id", "label": "Product", "field_type": "select", "required": True, "options_source": "products", "order_index": 1},
            {"key": "quantity", "label": "Quantity", "field_type": "number", "required": True, "min_value": 1, "order_index": 2},
            {"key": "unit_price", "label": "Unit Price (GMD)", "field_type": "number", "required": True, "min_value": 0, "order_index": 3},
            {"key": "channel", "label": "Sales Channel", "field_type": "select", "required": True, "options": [
                {"value": "AGENT", "label": "Agent Sales"},
                {"value": "STORE", "label": "Store Sales"},
                {"value": "WHOLESALE", "label": "Wholesale"},
            ], "default_value": "STORE", "order_index": 4},
            {"key": "customer_name", "label": "Customer Name", "field_type": "text", "required": False, "placeholder": "Optional", "order_index": 5},
            {"key": "notes", "label": "Notes", "field_type": "textarea", "required": False, "order_index": 6},
        ],
    },
    {
        "name": "Orders Form",
        "slug": "orders",
        "category": "order",
        "description": "Create new orders",
        "service_target": "orders.create_order",
        "fields": [
            {"key": "order_type", "label": "Order Type", "field_type": "select", "required": True, "options": [
                {"value": "AGENT_RESTOCK", "label": "Agent Restock"},
                {"value": "AGENT_RETAIL", "label": "Agent Retail"},
                {"value": "STORE_KEEPER_RESTOCK", "label": "Store Restock"},
                {"value": "CUSTOMER_WHOLESALE", "label": "Wholesale"},
            ], "order_index": 1},
            {"key": "product_id", "label": "Product", "field_type": "select", "required": True, "options_source": "products", "order_index": 2},
            {"key": "quantity", "label": "Quantity", "field_type": "number", "required": True, "min_value": 1, "order_index": 3},
            {"key": "priority", "label": "Priority", "field_type": "select", "required": False, "options": [
                {"value": "low", "label": "Low"},
                {"value": "normal", "label": "Normal"},
                {"value": "high", "label": "High"},
            ], "default_value": "normal", "order_index": 4},
            {"key": "notes", "label": "Notes", "field_type": "textarea", "required": False, "order_index": 5},
        ],
    },
    {
        "name": "Inventory Form",
        "slug": "inventory",
        "category": "inventory",
        "description": "Update inventory stock",
        "service_target": "inventory.update_stock",
        "fields": [
            {"key": "product_id", "label": "Product", "field_type": "select", "required": True, "options_source": "products", "order_index": 1},
            {"key": "adjustment_type", "label": "Adjustment Type", "field_type": "select", "required": True, "options": [
                {"value": "add", "label": "Add Stock"},
                {"value": "remove", "label": "Remove Stock"},
                {"value": "set", "label": "Set Stock Level"},
            ], "order_index": 2},
            {"key": "quantity", "label": "Quantity", "field_type": "number", "required": True, "min_value": 0, "order_index": 3},
            {"key": "reason", "label": "Reason", "field_type": "select", "required": True, "options": [
                {"value": "purchase", "label": "New Purchase"},
                {"value": "return", "label": "Customer Return"},
                {"value": "damage", "label": "Damaged Goods"},
                {"value": "transfer", "label": "Stock Transfer"},
                {"value": "correction", "label": "Inventory Correction"},
                {"value": "other", "label": "Other"},
            ], "order_index": 4},
            {"key": "notes", "label": "Notes", "field_type": "textarea", "required": False, "order_index": 5},
        ],
    },
    {
        "name": "Raw Materials Form",
        "slug": "raw_materials",
        "category": "raw_material",
        "description": "Manage raw materials inventory",
        "service_target": "inventory.update_raw_material",
        "fields": [
            {"key": "material_id", "label": "Raw Material", "field_type": "select", "required": True, "options_source": "raw_materials", "order_index": 1},
            {"key": "transaction_type", "label": "Transaction Type", "field_type": "select", "required": True, "options": [
                {"value": "ADD", "label": "Add Stock"},
                {"value": "USE", "label": "Use in Production"},
            ], "order_index": 2},
            {"key": "quantity", "label": "Quantity", "field_type": "number", "required": True, "min_value": 0.01, "order_index": 3},
            {"key": "unit_cost", "label": "Unit Cost (GMD)", "field_type": "number", "required": False, "min_value": 0, "help_text": "Required for ADD transactions", "order_index": 4},
            {"key": "supplier", "label": "Supplier", "field_type": "text", "required": False, "help_text": "Optional supplier name", "order_index": 5},
            {"key": "notes", "label": "Notes", "field_type": "textarea", "required": False, "order_index": 6},
        ],
    },
]


@router.post("/admin/seed", response_model=dict)
async def seed_forms(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Seed initial forms (Sales, Orders, Inventory, Raw Materials).
    Admin only. Will skip forms that already exist by slug.
    """
    await require_admin(db, current_user)
    
    created = []
    skipped = []
    
    for form_def in SEED_FORMS:
        # Check if form exists
        existing = await db.execute(select(Form).where(Form.slug == form_def["slug"]))
        if existing.scalar_one_or_none():
            skipped.append(form_def["slug"])
            continue
        
        # Create form
        form = Form(
            name=form_def["name"],
            slug=form_def["slug"],
            category=FormCategory(form_def["category"]),
            description=form_def.get("description"),
            service_target=form_def.get("service_target"),
            is_active=True,
            current_version=1,
            created_by_id=current_user["user_id"],
        )
        db.add(form)
        await db.flush()
        
        # Add fields
        for field_def in form_def.get("fields", []):
            field = FormField(
                form_id=form.id,
                key=field_def["key"],
                label=field_def["label"],
                field_type=FormFieldType(field_def["field_type"]),
                placeholder=field_def.get("placeholder"),
                help_text=field_def.get("help_text"),
                required=field_def.get("required", False),
                min_value=field_def.get("min_value"),
                max_value=field_def.get("max_value"),
                min_length=field_def.get("min_length"),
                max_length=field_def.get("max_length"),
                pattern=field_def.get("pattern"),
                options=json.dumps(field_def["options"]) if field_def.get("options") else None,
                options_source=field_def.get("options_source"),
                default_value=field_def.get("default_value"),
                role_visibility=json.dumps(field_def["role_visibility"]) if field_def.get("role_visibility") else None,
                order_index=field_def.get("order_index", 0),
                field_group=field_def.get("field_group"),
            )
            db.add(field)
        
        # Create initial version
        version = FormVersion(
            form_id=form.id,
            version=1,
            snapshot=json.dumps({
                "name": form.name,
                "slug": form.slug,
                "category": form.category.value,
                "description": form.description,
                "service_target": form.service_target,
                "fields": form_def.get("fields", []),
            }),
            change_notes="Initial form creation",
            created_by_id=current_user["user_id"],
        )
        db.add(version)
        
        created.append(form_def["slug"])
    
    await db.commit()
    
    return {
        "message": f"Seeding complete. Created: {len(created)}, Skipped (already exist): {len(skipped)}",
        "created": created,
        "skipped": skipped,
    }


# ============================================================================
# Admin Form CRUD with {form_id} parameter
# ============================================================================

@router.get("/admin/{form_id}", response_model=FormResponse)
async def get_form_admin(
    form_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Get full form definition with all fields.
    Admin only.
    """
    await require_admin(db, current_user)
    
    query = select(Form).options(selectinload(Form.fields)).where(Form.id == form_id)
    result = await db.execute(query)
    form = result.scalar_one_or_none()
    
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    return _form_to_response(form)


@router.patch("/admin/{form_id}", response_model=FormResponse)
async def update_form(
    form_id: int,
    payload: FormUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Update form definition.
    Admin only. Creates a new version.
    """
    await require_admin(db, current_user)
    
    query = select(Form).options(selectinload(Form.fields)).where(Form.id == form_id)
    result = await db.execute(query)
    form = result.scalar_one_or_none()
    
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    # Update fields
    if payload.name is not None:
        form.name = payload.name
    if payload.description is not None:
        form.description = payload.description
    if payload.category is not None:
        form.category = payload.category
    if payload.allowed_roles is not None:
        form.allowed_roles = _serialize_json_field(payload.allowed_roles)
    if payload.service_target is not None:
        form.service_target = payload.service_target
    if payload.field_mapping is not None:
        form.field_mapping = _serialize_json_field(payload.field_mapping)
    if payload.is_active is not None:
        form.is_active = payload.is_active
    
    # Increment version
    form.current_version = (form.current_version or 1) + 1
    
    # Create version snapshot
    await _create_version_snapshot(db, form, current_user["user_id"], "Form updated")
    
    await db.commit()
    await db.refresh(form)
    
    return _form_to_response(form)


@router.delete("/admin/{form_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_form(
    form_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Delete a form.
    Admin only. Cascades to fields and versions.
    """
    await require_admin(db, current_user)
    
    query = select(Form).where(Form.id == form_id)
    result = await db.execute(query)
    form = result.scalar_one_or_none()
    
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    await db.delete(form)
    await db.commit()


# ============================================================================
# Field Management Endpoints
# ============================================================================

@router.post("/admin/{form_id}/fields", response_model=FormFieldResponse, status_code=status.HTTP_201_CREATED)
async def add_field(
    form_id: int,
    payload: FormFieldCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Add a field to a form.
    Admin only.
    """
    await require_admin(db, current_user)
    
    # Get form
    query = select(Form).options(selectinload(Form.fields)).where(Form.id == form_id)
    result = await db.execute(query)
    form = result.scalar_one_or_none()
    
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    # Check key uniqueness within form
    existing_keys = [f.key for f in form.fields]
    if payload.key in existing_keys:
        raise HTTPException(status_code=400, detail=f"Field with key '{payload.key}' already exists in this form")
    
    field = FormField(
        form_id=form_id,
        key=payload.key,
        label=payload.label,
        field_type=payload.field_type,
        placeholder=payload.placeholder,
        help_text=payload.help_text,
        required=payload.required,
        min_value=payload.min_value,
        max_value=payload.max_value,
        min_length=payload.min_length,
        max_length=payload.max_length,
        pattern=payload.pattern,
        options=_serialize_json_field(payload.options),
        options_source=payload.options_source,
        default_value=payload.default_value,
        role_visibility=_serialize_json_field(payload.role_visibility),
        conditional_visibility=_serialize_json_field(payload.conditional_visibility),
        order_index=payload.order_index,
        field_group=payload.field_group,
    )
    db.add(field)
    
    # Update form version
    form.current_version = (form.current_version or 1) + 1
    await db.flush()
    
    # Create version snapshot
    await _create_version_snapshot(db, form, current_user["user_id"], f"Added field: {payload.key}")
    
    await db.commit()
    await db.refresh(field)
    
    return _field_to_response(field)


@router.patch("/admin/{form_id}/fields/{field_id}", response_model=FormFieldResponse)
async def update_field(
    form_id: int,
    field_id: int,
    payload: FormFieldUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Update a field.
    Admin only.
    """
    await require_admin(db, current_user)
    
    # Get form with fields
    form_query = select(Form).options(selectinload(Form.fields)).where(Form.id == form_id)
    form_result = await db.execute(form_query)
    form = form_result.scalar_one_or_none()
    
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    # Get field
    query = select(FormField).where(FormField.id == field_id, FormField.form_id == form_id)
    result = await db.execute(query)
    field = result.scalar_one_or_none()
    
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    
    # Check key uniqueness if changing key
    if payload.key is not None and payload.key != field.key:
        existing_keys = [f.key for f in form.fields if f.id != field_id]
        if payload.key in existing_keys:
            raise HTTPException(status_code=400, detail=f"Field with key '{payload.key}' already exists in this form")
    
    # Update fields
    if payload.key is not None:
        field.key = payload.key
    if payload.label is not None:
        field.label = payload.label
    if payload.field_type is not None:
        field.field_type = payload.field_type
    if payload.placeholder is not None:
        field.placeholder = payload.placeholder
    if payload.help_text is not None:
        field.help_text = payload.help_text
    if payload.required is not None:
        field.required = payload.required
    if payload.min_value is not None:
        field.min_value = payload.min_value
    if payload.max_value is not None:
        field.max_value = payload.max_value
    if payload.min_length is not None:
        field.min_length = payload.min_length
    if payload.max_length is not None:
        field.max_length = payload.max_length
    if payload.pattern is not None:
        field.pattern = payload.pattern
    if payload.options is not None:
        field.options = _serialize_json_field(payload.options)
    if payload.options_source is not None:
        field.options_source = payload.options_source
    if payload.default_value is not None:
        field.default_value = payload.default_value
    if payload.role_visibility is not None:
        field.role_visibility = _serialize_json_field(payload.role_visibility)
    if payload.conditional_visibility is not None:
        field.conditional_visibility = _serialize_json_field(payload.conditional_visibility)
    if payload.order_index is not None:
        field.order_index = payload.order_index
    if payload.field_group is not None:
        field.field_group = payload.field_group
    
    # Update form version
    form.current_version = (form.current_version or 1) + 1
    
    # Create version snapshot
    await _create_version_snapshot(db, form, current_user["user_id"], f"Updated field: {field.key}")
    
    await db.commit()
    await db.refresh(field)
    
    return _field_to_response(field)


@router.delete("/admin/{form_id}/fields/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_field(
    form_id: int,
    field_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Delete a field from a form.
    Admin only.
    """
    await require_admin(db, current_user)
    
    # Get form
    form_query = select(Form).options(selectinload(Form.fields)).where(Form.id == form_id)
    form_result = await db.execute(form_query)
    form = form_result.scalar_one_or_none()
    
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    # Get field
    query = select(FormField).where(FormField.id == field_id, FormField.form_id == form_id)
    result = await db.execute(query)
    field = result.scalar_one_or_none()
    
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    
    field_key = field.key
    await db.delete(field)
    
    # Update form version
    form.current_version = (form.current_version or 1) + 1
    
    # Create version snapshot
    await _create_version_snapshot(db, form, current_user["user_id"], f"Deleted field: {field_key}")
    
    await db.commit()


@router.post("/admin/{form_id}/fields/reorder", response_model=FormResponse)
async def reorder_fields(
    form_id: int,
    field_order: List[int],  # List of field IDs in desired order
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Reorder fields in a form.
    Admin only.
    """
    await require_admin(db, current_user)
    
    # Get form with fields
    query = select(Form).options(selectinload(Form.fields)).where(Form.id == form_id)
    result = await db.execute(query)
    form = result.scalar_one_or_none()
    
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    # Update order
    field_map = {f.id: f for f in form.fields}
    for idx, field_id in enumerate(field_order):
        if field_id in field_map:
            field_map[field_id].order_index = idx
    
    # Update form version
    form.current_version = (form.current_version or 1) + 1
    
    # Create version snapshot
    await _create_version_snapshot(db, form, current_user["user_id"], "Reordered fields")
    
    await db.commit()
    await db.refresh(form)
    
    return _form_to_response(form)


# ============================================================================
# Version Management Endpoints
# ============================================================================

@router.get("/admin/{form_id}/versions", response_model=List[FormVersionResponse])
async def list_versions(
    form_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    List all versions of a form.
    Admin only.
    """
    await require_admin(db, current_user)
    
    query = select(FormVersion).where(FormVersion.form_id == form_id).order_by(FormVersion.version.desc())
    result = await db.execute(query)
    versions = result.scalars().all()
    
    return [
        FormVersionResponse(
            id=v.id,
            version=v.version,
            change_notes=v.change_notes,
            created_at=v.created_at,
        )
        for v in versions
    ]


@router.get("/admin/{form_id}/versions/{version_id}")
async def get_version_snapshot(
    form_id: int,
    version_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Get the snapshot of a specific version.
    Admin only.
    """
    await require_admin(db, current_user)
    
    query = select(FormVersion).where(FormVersion.id == version_id, FormVersion.form_id == form_id)
    result = await db.execute(query)
    version = result.scalar_one_or_none()
    
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    
    return {
        "id": version.id,
        "version": version.version,
        "change_notes": version.change_notes,
        "created_at": version.created_at,
        "snapshot": json.loads(version.snapshot) if version.snapshot else None,
    }


@router.post("/admin/{form_id}/versions/{version_id}/restore", response_model=FormResponse)
async def restore_version(
    form_id: int,
    version_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Restore a form to a previous version.
    Admin only.
    """
    await require_admin(db, current_user)
    
    # Get form
    form_query = select(Form).options(selectinload(Form.fields)).where(Form.id == form_id)
    form_result = await db.execute(form_query)
    form = form_result.scalar_one_or_none()
    
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    # Get version
    version_query = select(FormVersion).where(FormVersion.id == version_id, FormVersion.form_id == form_id)
    version_result = await db.execute(version_query)
    version = version_result.scalar_one_or_none()
    
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    
    snapshot = json.loads(version.snapshot)
    
    # Update form from snapshot
    form.name = snapshot.get("name", form.name)
    form.description = snapshot.get("description")
    form.category = FormCategory(snapshot.get("category", "custom"))
    form.allowed_roles = _serialize_json_field(snapshot.get("allowed_roles"))
    form.service_target = snapshot.get("service_target")
    form.field_mapping = _serialize_json_field(snapshot.get("field_mapping"))
    form.is_active = snapshot.get("is_active", True)
    
    # Delete existing fields
    for field in form.fields:
        await db.delete(field)
    
    # Restore fields from snapshot
    for idx, field_data in enumerate(snapshot.get("fields", [])):
        field = FormField(
            form_id=form_id,
            key=field_data["key"],
            label=field_data["label"],
            field_type=FormFieldType(field_data["field_type"]),
            placeholder=field_data.get("placeholder"),
            help_text=field_data.get("help_text"),
            required=field_data.get("required", False),
            min_value=field_data.get("min_value"),
            max_value=field_data.get("max_value"),
            min_length=field_data.get("min_length"),
            max_length=field_data.get("max_length"),
            pattern=field_data.get("pattern"),
            options=_serialize_json_field(field_data.get("options")),
            options_source=field_data.get("options_source"),
            default_value=field_data.get("default_value"),
            role_visibility=_serialize_json_field(field_data.get("role_visibility")),
            conditional_visibility=_serialize_json_field(field_data.get("conditional_visibility")),
            order_index=field_data.get("order_index", idx),
            field_group=field_data.get("field_group"),
        )
        db.add(field)
    
    # Increment version
    form.current_version = (form.current_version or 1) + 1
    
    # Create new version snapshot
    await db.flush()
    await _create_version_snapshot(db, form, current_user["user_id"], f"Restored from version {version.version}")
    
    await db.commit()
    
    # Re-fetch with fields
    query = select(Form).options(selectinload(Form.fields)).where(Form.id == form_id)
    result = await db.execute(query)
    form = result.scalar_one()
    
    return _form_to_response(form)


# ============================================================================
# Public Endpoints (for form rendering)
# ============================================================================

@router.get("/{slug}", response_model=FormResponse)
async def get_form_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Get form definition by slug for rendering.
    Returns fields filtered by user's role.
    Public endpoint (authenticated).
    """
    query = select(Form).options(selectinload(Form.fields)).where(Form.slug == slug, Form.is_active == True)
    result = await db.execute(query)
    form = result.scalar_one_or_none()
    
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    # Check role access
    allowed_roles = _parse_json_field(form.allowed_roles)
    user_role = current_user.get("role", "member")
    
    if not _check_role_access(user_role, allowed_roles):
        raise HTTPException(status_code=403, detail="You don't have permission to access this form")
    
    # Get full response then filter fields
    response = _form_to_response(form)
    response.fields = _filter_fields_by_role(response.fields, user_role)
    
    return response


@router.get("/")
async def list_available_forms(
    category: Optional[FormCategory] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    List forms available to the current user.
    Filters by role access.
    """
    query = select(Form).where(Form.is_active == True)
    
    if category:
        query = query.where(Form.category == category)
    
    query = query.order_by(Form.category, Form.name)
    
    result = await db.execute(query)
    forms = result.scalars().all()
    
    # Filter by role access
    user_role = current_user.get("role", "member")
    available = []
    
    for form in forms:
        allowed_roles = _parse_json_field(form.allowed_roles)
        if _check_role_access(user_role, allowed_roles):
            available.append({
                "id": form.id,
                "slug": form.slug,
                "name": form.name,
                "category": form.category.value if hasattr(form.category, 'value') else form.category,
                "description": form.description,
            })
    
    return available


# ============================================================================
# Form Submission Endpoint
# ============================================================================

@router.post("/{slug}/submit", response_model=FormSubmissionResponse)
async def submit_form(
    slug: str,
    payload: FormSubmissionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Submit a form.
    
    The submission is:
    1. Validated against form definition
    2. Role-checked
    3. Routed to the appropriate service (sales, orders, etc.)
    4. Recorded for audit
    
    Returns the submission record with result from the target service.
    """
    from app.services.form_submission import FormSubmissionService
    
    # Get form with fields
    query = select(Form).options(selectinload(Form.fields)).where(Form.slug == slug, Form.is_active == True)
    result = await db.execute(query)
    form = result.scalar_one_or_none()
    
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    # Check role access
    allowed_roles = _parse_json_field(form.allowed_roles)
    user_role = current_user.get("role", "member")
    
    if not _check_role_access(user_role, allowed_roles):
        raise HTTPException(status_code=403, detail="You don't have permission to submit this form")
    
    # Validate required fields
    missing = FormSubmissionService.validate_required_fields(form, payload.data)
    if missing:
        raise HTTPException(
            status_code=400, 
            detail=f"Missing required fields: {', '.join(missing)}"
        )
    
    # Create submission record
    submission = FormSubmission(
        form_id=form.id,
        form_version=form.current_version or 1,
        data=json.dumps(payload.data),
        service_target=form.service_target,
        status="pending",
        submitted_by_id=current_user["user_id"],
    )
    db.add(submission)
    await db.flush()
    
    # Route to service
    status_result, result_id, error_message = await FormSubmissionService.submit(
        db=db,
        form=form,
        data=payload.data,
        user_id=current_user["user_id"],
    )
    
    # Update submission record
    submission.status = status_result
    submission.result_id = result_id
    submission.result_type = form.service_target
    submission.error_message = error_message
    
    await db.commit()
    await db.refresh(submission)
    
    if status_result == "failed":
        raise HTTPException(status_code=400, detail=error_message or "Form submission failed")
    
    return FormSubmissionResponse(
        id=submission.id,
        form_id=submission.form_id,
        form_version=submission.form_version,
        status=submission.status,
        result_id=submission.result_id,
        result_type=submission.result_type,
        error_message=submission.error_message,
        created_at=submission.created_at,
    )


@router.get("/{slug}/submissions", response_model=List[FormSubmissionResponse])
async def list_submissions(
    slug: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    List submissions for a form.
    Admin only.
    """
    await require_admin(db, current_user)
    
    # Get form
    form_query = select(Form).where(Form.slug == slug)
    form_result = await db.execute(form_query)
    form = form_result.scalar_one_or_none()
    
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    query = (
        select(FormSubmission)
        .where(FormSubmission.form_id == form.id)
        .order_by(FormSubmission.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    
    result = await db.execute(query)
    submissions = result.scalars().all()
    
    return [
        FormSubmissionResponse(
            id=s.id,
            form_id=s.form_id,
            form_version=s.form_version,
            status=s.status,
            result_id=s.result_id,
            result_type=s.result_type,
            error_message=s.error_message,
            created_at=s.created_at,
        )
        for s in submissions
    ]


@router.get("/{slug}/submissions/{submission_id}")
async def get_submission(
    slug: str,
    submission_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Get a specific submission with full data.
    Admin only.
    """
    await require_admin(db, current_user)
    
    # Get form
    form_query = select(Form).where(Form.slug == slug)
    form_result = await db.execute(form_query)
    form = form_result.scalar_one_or_none()
    
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    query = select(FormSubmission).where(
        FormSubmission.id == submission_id,
        FormSubmission.form_id == form.id,
    )
    result = await db.execute(query)
    submission = result.scalar_one_or_none()
    
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    return {
        "id": submission.id,
        "form_id": submission.form_id,
        "form_version": submission.form_version,
        "data": json.loads(submission.data) if submission.data else {},
        "service_target": submission.service_target,
        "result_id": submission.result_id,
        "result_type": submission.result_type,
        "status": submission.status,
        "error_message": submission.error_message,
        "submitted_by_id": submission.submitted_by_id,
        "created_at": submission.created_at,
    }
