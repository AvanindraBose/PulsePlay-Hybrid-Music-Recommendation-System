import json
import os
import bcrypt
import hashlib
from datetime import datetime, timezone ,timedelta
from jose import JWTError , jwt , ExpiredSignatureError
from backend.core.config import settings
from backend.logging_fastapi.logger_api import auth_logger
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS"))
# --> Old Logic
# def create_token(data:dict , expire_minutes=30):
#     to_encode = data.copy()
#     expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
#     to_encode.update({"exp" : expire})
    
#     return jwt.encode(
#         to_encode,
#         key=settings.JWT_SECRET_KEY,
#         algorithm= settings.JWT_ALGORITHM
#     )

# Replacing New Logic with Access and Refresh Tokens

def create_access_tokens(user_id:str):
    try:
        auth_logger.save_logs(f"Creating access token for user_id: {user_id}",log_level="info")
        now  = datetime.now(timezone.utc)

        payload = {
        "sub":user_id,
        "token_type":"access",
        "iat":now,
        "exp" : now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        }

        token = jwt.encode(
        payload,
        settings.JWT_ACCESS_SECRET_KEY,
        settings.JWT_ALGORITHM  
        )

    except Exception as e:
        auth_logger.save_logs(f"Error creating access token: {str(e)}",log_level="error")
        raise e
    else:
        auth_logger.save_logs(f"Access token created successfully for user_id: {user_id}",log_level="info")
        return token

# Refresh Tokens

def create_refresh_tokens(user_id:str):
    try:
        auth_logger.save_logs(f"Creating refresh token for user_id: {user_id}",log_level="info")
        now  = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        payload = {
        "sub":user_id,
        "token_type":"refresh",
        "iat":now,
        "exp" : expires_at
        }

        token = jwt.encode(
        payload,
        settings.JWT_REFRESH_SECRET_KEY,
        settings.JWT_ALGORITHM  
        )
    except Exception as e:
        auth_logger.save_logs(f"Error creating refresh token: {str(e)}" , log_level="error")
        raise e
    else:
        auth_logger.save_logs(f"Refresh token created successfully for user_id: {user_id}",log_level="info")
        return token,expires_at


# def verify_token(token:str):
#     try:
#         payload = jwt.decode(token,key=settings.JWT_SECRET_KEY,algorithms=[settings.JWT_ALGORITHM])
#         return payload
#     except JWTError:
#         return None

def verify_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_ACCESS_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )

        if payload.get("token_type") != "access":
            auth_logger.save_logs(
                f"Invalid access token type: {payload.get('token_type')}",
                log_level="warning"
            )
            return {
                "payload": None,
                "error": "invalid_token_type"
            }

        return {
            "payload": payload,
            "error": None
        }

    except ExpiredSignatureError:
        auth_logger.save_logs(
            "Access token expired",
            log_level="warning"
        )
        return {
            "payload": None,
            "error": "expired"
        }

    except JWTError as e:
        auth_logger.save_logs(
            f"JWTError while verifying access token: {str(e)}",
            log_level="error"
        )
        return {
            "payload": None,
            "error": "invalid"
        }

    except JWTError:
        auth_logger.save_logs(f"JWTError while verifying access token: {str(JWTError)}", log_level="error")
        return None

def verify_refresh_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_REFRESH_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )

        if payload.get("token_type") != "refresh":
            auth_logger.save_logs(
                f"Invalid refresh token type: {payload.get('token_type')}",
                log_level="warning"
            )
            return {
                "payload": None,
                "error": "invalid_token_type"
            }

        return {
            "payload": payload,
            "error": None
        }

    except ExpiredSignatureError:
        auth_logger.save_logs(
            "Refresh token expired",
            log_level="warning"
        )
        return {
            "payload": None,
            "error": "expired"
        }

    except JWTError as e:
        auth_logger.save_logs(
            f"JWTError while verifying refresh token: {str(e)}",
            log_level="error"
        )
        return {
            "payload": None,
            "error": "invalid"
        }


def hash_password(password:str)-> str:
    return bcrypt.hashpw(
        password.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')

def verify_password(password:str , hashed_password:str)-> bool:
    return bcrypt.checkpw(
        password.encode("utf-8"),
        hashed_password.encode("utf-8")
    )

def hash_refresh_token(token:str)->str:
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()

def verify_hashed_refresh_token(token:str ,hashed_token:str)-> bool:
    return hash_refresh_token(token) == hashed_token


def make_cache_key(data:dict):
    data_string = json.dumps(data,sort_keys=True)
    return hashlib.sha256(data_string.encode()).hexdigest()