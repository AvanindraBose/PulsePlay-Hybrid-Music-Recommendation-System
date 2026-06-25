from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from backend.core.dependencies import get_db,get_redis_client
from backend.logging_fastapi.logger_api import health_logger
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from backend.core.config import settings

router = APIRouter(prefix="/internal" , tags=["Health"])

@router.get("/health")
async def health_check(
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis_client)
):
    health_logger.save_logs("Health check initiated",log_level='info')

    db_status = "ok"
    redis_status = "ok"

    # 🔹 DB check
    try:
        await db.execute(text("SELECT 1"))
        health_logger.save_logs("Database connection successful",log_level="info")
    except Exception as e:
        health_logger.save_logs(f"Database connection failed: {e}",log_level="error")
        db_status = "error"

    # 🔹 Redis check
    try:
        await redis.ping()
        health_logger.save_logs("Redis connection successful",log_level="info")
    except Exception as e:
        health_logger.save_logs(f"Redis connection failed: {e}",log_level="error")
        redis_status = "error"


    if db_status == "ok" and redis_status == "ok":
        return {"status": "ok"}

    return {
        "status": "error",
        "details": {
            "database": db_status,
            "redis": redis_status
        }
    }
