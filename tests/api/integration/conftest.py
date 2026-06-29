import pandas as pd
import pytest
import pytest_asyncio
from collections.abc import AsyncIterator
from urllib.parse import unquote
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine.url import make_url
from backend.core.database import Base, engine
from backend.loader.redis_loader import close_redis_client, load_redis_client
from backend.main import app


LOCAL_DB_HOSTS = {"127.0.0.1", "localhost", "postgres"}
TEST_DATABASE_NAME = "pulse_play_test"


def pytest_collection_modifyitems(items):
    session_loop = pytest.mark.asyncio(loop_scope="session")
    for item in items:
        item.add_marker(session_loop)


def _assert_local_database() -> None:
    db_url = make_url(str(engine.url))
    host = unquote(db_url.host or "")
    database = unquote(db_url.database or "")

    if host not in LOCAL_DB_HOSTS or database != TEST_DATABASE_NAME:
        raise RuntimeError(
            "Integration tests must run against a local disposable database. "
            f"Refusing to use DATABASE_URL host={host!r}, database={database!r}."
        )


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def integration_services() -> AsyncIterator[None]:
    _assert_local_database()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    redis = await load_redis_client()
    await redis.flushdb()

    yield

    await redis.flushdb()
    await close_redis_client()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(loop_scope="session", autouse=True)
async def clean_integration_state() -> AsyncIterator[None]:
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(text(f'TRUNCATE TABLE "{table.name}" RESTART IDENTITY CASCADE'))

    redis = await load_redis_client()
    await redis.flushdb()

    yield


@pytest_asyncio.fixture(loop_scope="session")
async def integration_app():
    app.dependency_overrides.clear()
    app.state.songs_data = pd.DataFrame([{"name": "blinding lights", "artist": "the weeknd"}])
    app.state.filtered_data = pd.DataFrame([{"name": "blinding lights", "artist": "the weeknd"}])
    app.state.transformed_data = object()
    app.state.track_ids = ["track-1"]
    app.state.interaction_matrix = object()
    app.state.hybrid_transformed = object()

    yield app

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(loop_scope="session")
async def integration_async_client(integration_app) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=integration_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
