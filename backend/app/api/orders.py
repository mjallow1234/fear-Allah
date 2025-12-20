from fastapi import APIRouter, Depends, HTTPException, status
from app.core.security import get_current_user
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from pydantic import BaseModel
from app.services.task_engine import create_order

router = APIRouter()


class CreateOrderRequest(BaseModel):
    order_type: str
    items: list = []
    metadata: dict = {}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_order_endpoint(request: CreateOrderRequest, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        order = await create_order(db, request.order_type, items=str(request.items), metadata=str(request.metadata))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"order_id": order.id, "status": order.status}