from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.database import get_db
from app.core.config import settings, logger
from app.core.redis import redis_client

router = APIRouter()

@router.get('/healthz')
def healthz():
    return {"status": "ok"}

@router.get('/readyz')
async def readyz(db: AsyncSession = Depends(get_db)):
    # Check DB connectivity
    try:
        await db.execute(text('SELECT 1'))
    except Exception as e:
        logger.exception('Readiness DB check failed')
        raise HTTPException(status_code=503, detail='Not ready')

    # Check Redis only if web sockets are enabled (feature flag)
    if settings.WS_ENABLED:
        try:
            if not redis_client.health_check():
                logger.error('Redis health check failed')
                raise HTTPException(status_code=503, detail='Not ready')
        except HTTPException:
            raise
        except Exception:
            logger.exception('Redis readiness check failed')
            raise HTTPException(status_code=503, detail='Not ready')

    return {"status": "ready"}