from fastapi import APIRouter, Depends, HTTPException, status
from app.core.security import get_current_user
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from sqlalchemy import select
from app.db.models import Task
from app.services.task_engine import complete_task

router = APIRouter()

# Task stage color codes for UI
TASK_STATUS_COLORS = {
    "pending": "#9CA3AF",    # Gray - waiting
    "active": "#3B82F6",     # Blue - in progress
    "done": "#10B981",       # Green - completed
}

TASK_STEP_COLORS = {
    # Foreman steps - Orange/Amber
    "assemble_items": "#F59E0B",
    "foreman_handover": "#D97706",
    # Delivery steps - Purple
    "delivery_received": "#8B5CF6",
    "deliver_items": "#7C3AED",
    "accept_delivery": "#A855F7",
    # Requester/Confirmation steps - Teal
    "confirm_received": "#14B8A6",
}


@router.get("/")
async def list_tasks(assigned_to: str = None, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.db.models import Order, Sale
    from sqlalchemy import select

    q = select(Task)
    if assigned_to == 'me':
        q = q.where(Task.assigned_user_id == current_user['user_id'], Task.status.in_(['active', 'pending']))
    result = await db.execute(q)
    tasks = result.scalars().all()

    # Gather all order_ids from tasks
    order_ids = [t.order_id for t in tasks if t.order_id]
    sales_order_ids = set()
    if order_ids:
        sales_rows = await db.execute(
            select(Sale.related_order_id)
            .where(Sale.related_order_id.in_(order_ids), Sale.is_reversed == False)
        )
        sales_order_ids = set(sales_rows.scalars().all())

    # Optionally, fetch order info for each task (for future extensibility)
    order_map = {o.id: o for o in (await db.execute(select(Order).where(Order.id.in_(order_ids)))).scalars().all()} if order_ids else {}

    return [
        {
            "task_id": t.id,
            "order_id": t.order_id,
            "step_key": t.step_key,
            "status": t.status,
            "assigned_user_id": t.assigned_user_id,
            "status_color": TASK_STATUS_COLORS.get(t.status, "#6B7280"),
            "step_color": TASK_STEP_COLORS.get(t.step_key, "#6B7280"),
            "order": {
                "id": t.order_id,
                "has_sale": t.order_id in sales_order_ids,
                # Optionally add more order fields here if needed
            } if t.order_id else None,
        }
        for t in tasks
    ]


@router.post("/{task_id}/complete")
async def complete_task_endpoint(task_id: int, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        task, next_task, order = await complete_task(db, task_id, current_user['user_id'])
    except ValueError:
        raise HTTPException(status_code=404, detail="Task not found")
    except PermissionError as e:
        # Map permission errors to 403 or 409
        if str(e) == "Task is not active":
            raise HTTPException(status_code=409, detail=str(e))
        else:
            raise HTTPException(status_code=403, detail=str(e))
    except RuntimeError as e:
        # Optimistic lock conflict
        raise HTTPException(status_code=409, detail=str(e))

    return {"task_id": task.id, "status": task.status, "order_status": order.status}