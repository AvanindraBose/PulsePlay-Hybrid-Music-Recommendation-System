from backend.logging_fastapi.logger_api import health_logger,auth_logger
from fastapi import Header,HTTPException,status,Request
# from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.core.config import settings
from backend.core.security import verify_access_token , verify_refresh_token
from backend.core.database import AsyncSessionLocal
from typing import AsyncGenerator
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
# from backend.loader.artifacts_loader import load_artifacts
from backend.loader.redis_loader import load_redis_client

load_dotenv()

# try:
#     mlflow.set_tracking_uri(os.getenv('MLFLOW_TRACKING_URI'))
#     dagshub.init(repo_owner='AvanindraBose', repo_name='Twitter-Sentiment-Detection', mlflow=True)
#     client = MlflowClient()
# except Exception as e:
#     prediction_logger.save_logs(f"Error occurred while initializing MLflow: {str(e)}", log_level="error")

# def get_api_key(api_key:str = Header(...)):
#     if api_key != settings.API_KEY:
#         health_logger.save_logs("Invalid API Key" , log_level='Warning')
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Invalid API Key"
#         )

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            auth_logger.save_logs("Database session initialized successfully", log_level="info")
        # except Exception as e:
        #     auth_logger.save_logs(f"Error occurred while initializing database session: {str(e)}", log_level="error")
        #     raise HTTPException(
        #         status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        #         detail="Database connection error"
        #     )
        finally:
            await session.close()
            auth_logger.save_logs("Database session closed", log_level="info")


# def get_current_user(
#         credentials:HTTPAuthorizationCredentials = Depends(security)
# ):
#     token = credentials.credentials
#     payload = verify_access_token(token)
#     if payload is None:
#         raise HTTPException(
#             status_code = status.HTTP_401_UNAUTHORIZED,
#             detail = "Invalid or expired access token"
#         )
    
#     return payload["sub"]

def get_current_user(request: Request) -> str:
    access_token = request.cookies.get("access_token")

    if not access_token:
        auth_logger.save_logs(
            "Access token not found in cookies",
            log_level="warning"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing_access_token"
        )

    token_result = verify_access_token(access_token)
    payload = token_result["payload"]
    error = token_result["error"]

    if payload is None:
        auth_logger.save_logs(
            f"Access token verification failed: {error}",
            log_level="warning"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error
        )

    user_id = payload.get("sub")

    if not user_id:
        auth_logger.save_logs(
            "User ID not found in access token payload",
            log_level="error"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_session"
        )

    return user_id




# def get_redis_client() -> Redis:
#     try: 
#         auth_logger.save_logs("Attempting to connect to Redis", log_level="info")
#         return Redis.from_url(
#             REDIS_URL,
#             decode_responses=True,
#             socket_timeout=2,
#             socket_connect_timeout=2,
#         )
#     except Exception:
#         auth_logger.save_logs("Failed to connect to Redis", log_level="error")
#         raise HTTPException(
#             status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
#             detail="Service Temporarily Unavailable",
#         )

# loading Model

# async def get_artifacts():
#     return await load_artifacts()

# # loading Redis

async def get_redis_client() -> Redis:
    return await load_redis_client()
    
    
def get_refresh_user_id(request: Request) -> str:
    # print("Cookies:", request.cookies) 
    refresh_token = request.cookies.get("refresh_token")

    if not refresh_token:
        auth_logger.save_logs(
            "Refresh token missing in request cookies",
            log_level="warning"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    token_result = verify_refresh_token(refresh_token)
    payload = token_result["payload"]
    error = token_result["error"]

    if not payload:
        auth_logger.save_logs(
            f"{error}",
            log_level="warning"
        )
        return None

    user_id = payload.get("sub")

    if not user_id:
        auth_logger.save_logs(
            "Refresh token payload missing user_id",
            log_level="warning"
        )
        return None

    return user_id