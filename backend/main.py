from fastapi import FastAPI
from backend.api import routes_predict,routes_auth,routes_health,routes_root
from backend.core.database import engine,Base
# from backend.middlewares.response_logger import ResponseLoggerMiddleware
from fastapi.staticfiles import StaticFiles
from backend.logging_fastapi.logger_api import auth_logger
from contextlib import asynccontextmanager
from backend.loader.redis_loader import close_redis_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        auth_logger.save_logs("Database Connection Established successfully.")

    yield

    # Shutdown
    await close_redis_client()
    await engine.dispose()
    auth_logger.save_logs("Database Connection Closed successfully.")

app = FastAPI(title="Twitter Sentiment Detection API", description="API for detecting sentiment in tweets", version="1.0",lifespan=lifespan)
# app.add_middleware(ResponseLoggerMiddleware)

app.mount("/static", StaticFiles(directory="backend/static"), name="static")
# app.add_middleware(ResponseLoggerMiddleware)
app.include_router(routes_root.router,tags = ["Root"])
app.include_router(routes_predict.router , tags=["Predict"])
app.include_router(routes_auth.router , tags=["Auth"])
app.include_router(routes_health.router , tags=["Health"])