from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
from app.core.security import get_current_user
from app.db.database import get_db
from app.services.sales import record_sale
from app.db.models import Sale, Inventory, User

router = APIRouter()


@router.post("/")
async def create_sale(payload: dict, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        product_id = int(payload.get('product_id'))
        quantity = int(payload.get('quantity'))
        unit_price = float(payload.get('unit_price'))
        sale_channel = payload.get('sale_channel')
        related_order_id = payload.get('related_order_id')
        idempotency_key = payload.get('idempotency_key')
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid payload")

    try:
        sale = await record_sale(db, product_id, quantity, unit_price, current_user['user_id'], sale_channel=sale_channel, related_order_id=related_order_id, idempotency_key=idempotency_key)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return {"sale_id": sale.id, "product_id": sale.product_id, "quantity": sale.quantity}


@router.get("/metrics/daily")
async def daily_sales_totals(date: str | None = Query(None, description="ISO date YYYY-MM-DD. Defaults to today."), db: AsyncSession = Depends(get_db)):
    # parse date (UTC)
    if date:
        try:
            d = datetime.fromisoformat(date)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid date format, use YYYY-MM-DD")
    else:
        d = datetime.utcnow()
    start = datetime(d.year, d.month, d.day)
    end = start + timedelta(days=1)

    q = select(func.coalesce(func.sum(Sale.total_amount), 0), func.coalesce(func.sum(Sale.quantity), 0)).where(Sale.created_at >= start, Sale.created_at < end)
    res = await db.execute(q)
    total_amount, total_quantity = res.one()
    return {"date": start.date().isoformat(), "total_amount": float(total_amount), "total_quantity": int(total_quantity)}


@router.get("/inventory")
async def inventory_remaining(db: AsyncSession = Depends(get_db)):
    q = select(Inventory.product_id, Inventory.total_stock, Inventory.total_sold)
    res = await db.execute(q)
    rows = res.all()
    return [{"product_id": r[0], "total_stock": r[1], "total_sold": r[2], "remaining": r[1]} for r in rows]


@router.get("/grouped/channel")
async def sales_grouped_by_channel(db: AsyncSession = Depends(get_db)):
    q = select(Sale.sale_channel, func.coalesce(func.sum(Sale.total_amount), 0), func.coalesce(func.sum(Sale.quantity), 0)).group_by(Sale.sale_channel)
    res = await db.execute(q)
    return [{"channel": r[0], "total_amount": float(r[1]), "total_quantity": int(r[2])} for r in res.all()]


@router.get("/grouped/user")
async def sales_grouped_by_user(db: AsyncSession = Depends(get_db)):
    q = select(Sale.sold_by_user_id, func.coalesce(func.sum(Sale.total_amount), 0), func.coalesce(func.sum(Sale.quantity), 0))
    q = q.group_by(Sale.sold_by_user_id)
    res = await db.execute(q)
    rows = res.all()

    results = []
    for user_id, total_amount, total_quantity in rows:
        username = None
        if user_id is not None:
            u_q = select(User.username).where(User.id == user_id)
            u_res = await db.execute(u_q)
            u_row = u_res.scalar_one_or_none()
            username = u_row
        results.append({"user_id": user_id, "username": username, "total_amount": float(total_amount), "total_quantity": int(total_quantity)})
    return results


@router.get("/{sale_id}/commission")
async def sale_commission_classification(sale_id: int, db: AsyncSession = Depends(get_db)):
    from app.services.sales import classify_sale
    try:
        result = await classify_sale(db, sale_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Sale not found")
    return result