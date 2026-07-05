import json
import pandas as pd
from backend.core.dependencies  import get_redis_client
from backend.logging_fastapi.logger_api import prediction_logger
from backend.custom_metrics import CACHE_HITS, CACHE_MISSES, CACHE_WRITES
from backend.core.config import settings
from typing import Optional

async def get_cached_prediction(key:str,scope:str)-> Optional[dict]:
    try:
        redis_client = await get_redis_client()
        value = await redis_client.get(key)
        if value:
            # record cache hit
            CACHE_HITS.labels(scope=scope).inc()    
            return json.loads(value)
        else:
            # record cache miss          
            CACHE_MISSES.labels(scope=scope).inc()       
            return None
        
    except Exception as e:
        prediction_logger.save_logs(f"Error retrieving cached prediction: {e}", log_level="error")
        return None

async def set_cached_prediction(key:str,value:dict, scope:str, ttl:int = settings.REDIS_TTL)-> None:
    try:
        redis_client = await get_redis_client()
        await redis_client.setex(key,ttl,json.dumps(value))
        # record cache write
        CACHE_WRITES.labels(scope=scope).inc()
        prediction_logger.save_logs(f"Cached prediction set with key", log_level="info")
    except Exception as e:
        prediction_logger.save_logs(f"Error setting cached prediction: {e}", log_level="error")