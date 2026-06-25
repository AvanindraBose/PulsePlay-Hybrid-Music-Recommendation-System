from redis.asyncio import Redis
from backend.logging_fastapi.logger_api import prediction_logger
from backend.core.config import settings
from fastapi import HTTPException,status

REDIS_URL = settings.REDIS_URL
redis_client: Redis | None = None


async def load_redis_client() -> Redis:
    global redis_client

    if redis_client:
        prediction_logger.save_logs("Using cached Redis client", log_level="info")
        return redis_client

    try:
        prediction_logger.save_logs(
            "Attempting to connect to Redis",
            log_level="info"
        )

        client = Redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_timeout=2,
            socket_connect_timeout=2,
        )

        await client.ping()

        prediction_logger.save_logs(
            "Successfully connected to Redis",
            log_level="info"
        )

        redis_client = client
        return redis_client

    except Exception as e:
        prediction_logger.save_logs(
            f"Failed to connect to Redis | Error: {str(e)}",
            log_level="error"
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service Temporarily Unavailable",
        )

async def close_redis_client() -> Redis:
    global redis_client

    if redis_client is not None :
        await redis_client.aclose()
        redis_client = None
        prediction_logger.save_logs(
            "Redis Connection Closed Successfully",
            log_level="info"
        )