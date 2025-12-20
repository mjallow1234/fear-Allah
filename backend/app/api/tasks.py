from fastapi import APIRouter, Depends, HTTPException, status
from app.core.security import get_current_user
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from sqlalchemy import select
from app.db.models import Task
from app.services.task_engine import complete_task

router = APIRouter()


@router.get("/")
async def list_tasks(assigned_to: str = None, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    q = select(Task)
    if assigned_to == 'me':
        q = q.where(Task.assigned_user_id == current_user['user_id'], Task.status.in_(['ACTIVE', 'PENDING']))
    result = await db.execute(q)
    tasks = result.scalars().all()
    return [
        {
            "task_id": t.id,
            "order_id": t.order_id,
            "step_key": t.step_key,
            "status": t.status,
            "assigned_user_id": t.assigned_user_id,
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