from fastapi import FastAPI
from backend.api import routes_auth,routes_health,routes_root
from backend.core.database import engine,Base
from fastapi.staticfiles import StaticFiles
from backend.logging_fastapi.logger_api import auth_logger
from contextlib import asynccontextmanager
from backend.loader.redis_loader import close_redis_client
from backend.loader.asset_loader import load_datasets

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        auth_logger.save_logs("Database Connection Established successfully.")
   
    await load_datasets(app)

    yield

    # Shutdown
    await close_redis_client()
    await engine.dispose()
    auth_logger.save_logs("Database Connection Closed successfully.")

app = FastAPI(title="Twitter Sentiment Detection API", description="API for detecting sentiment in tweets", version="1.0",lifespan=lifespan)

app.mount("/static", StaticFiles(directory="backend/static"), name="static")
app.include_router(routes_root.router,tags = ["Root"])
app.include_router(routes_auth.router , tags=["Auth"])
app.include_router(routes_health.router , tags=["Health"])