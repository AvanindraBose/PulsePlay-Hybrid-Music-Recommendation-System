import time
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from backend.core.dependencies import get_db,get_redis_client
from backend.logging_fastapi.logger_api import health_logger
from backend.custom_metrics import (
    REQUEST_COUNT,
    REQUEST_DURATION,
    REQUEST_ERRORS,
    RESPONSE_STATUS,
)
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from backend.core.config import settings

router = APIRouter(prefix="/internal" , tags=["Health"])


def _record_request_metrics(method: str, endpoint: str, status_code: str, start_time: float, error_type: str | None = None) -> None:
    REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(time.perf_counter() - start_time)
    RESPONSE_STATUS.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
    if error_type:
        REQUEST_ERRORS.labels(method=method, endpoint=endpoint, error_type=error_type).inc()

@router.get("/health")
async def health_check(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis_client)
):
    start_time = time.perf_counter()
    endpoint = request.url.path
    method = request.method
    status_code = str(status.HTTP_200_OK)
    REQUEST_COUNT.labels(method=method, endpoint=endpoint).inc()

    health_logger.save_logs("Health check initiated",log_level='info')

    state = request.app.state

    db_status = "ok"
    redis_status = "ok"
    loader_status = "ok"

    # 🔹 Loader check
    try: 
        health = {
        "songs_data": hasattr(state, "songs_data"),
        "transformed_data": hasattr(state, "transformed_data"),
        "track_ids": hasattr(state, "track_ids"),
        "filtered_data": hasattr(state, "filtered_data"),
        "interaction_matrix": hasattr(state, "interaction_matrix"),
        "hybrid_transformed": hasattr(state, "hybrid_transformed"),
        }
    except Exception as e :
        health_logger.save_logs(f"Database connection failed: {e}",log_level="error")
        loader_status = "error"

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


    if db_status == "ok" and redis_status == "ok" and loader_status=="ok":
        try:
            return {"status": "ok"}
        finally:
            _record_request_metrics(method, endpoint, status_code, start_time)

    status_code = str(status.HTTP_500_INTERNAL_SERVER_ERROR)
    REQUEST_ERRORS.labels(method=method, endpoint=endpoint, error_type="server_error").inc()
    try:
        return {
            "status": "error",
            "details": {
                "database": db_status,
                "redis": redis_status,
                "loader": loader_status
            }
        }
    finally:
        _record_request_metrics(method, endpoint, status_code, start_time)
