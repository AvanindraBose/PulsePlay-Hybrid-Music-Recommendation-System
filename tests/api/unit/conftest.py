from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pandas as pd
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import dependencies
from backend.main import app


class FakeRedis:
    def __init__(self):
        self.store = {}

    async def ping(self) -> bool:
        return True

    async def get(self, key: str):
        return self.store.get(key)

    async def setex(self, key: str, seconds: int, value):
        self.store[key] = str(value)

    async def incr(self, key: str):
        self.store[key] = str(int(self.store.get(key, 0)) + 1)


@pytest.fixture
def fake_db() -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    return session


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def unit_app(fake_db: AsyncMock, fake_redis: FakeRedis):
    async def override_get_db():
        yield fake_db

    async def override_get_redis():
        return fake_redis

    async def override_get_current_user():
        return "test-user"

    app.dependency_overrides[dependencies.get_db] = override_get_db
    app.dependency_overrides[dependencies.get_redis_client] = override_get_redis
    app.dependency_overrides[dependencies.get_current_user] = override_get_current_user

    app.state.songs_data = pd.DataFrame(
        [
            {
                "name": "blinding lights",
                "artist": "the weeknd",
                "pulse_play_preview_url": "https://example.com/blinding.mp3",
            }
        ]
    )
    app.state.filtered_data = pd.DataFrame(
        [
            {
                "name": "blinding lights",
                "artist": "the weeknd",
                "pulse_play_preview_url": "https://example.com/blinding.mp3",
            }
        ]
    )
    app.state.transformed_data = object()
    app.state.track_ids = ["track-1"]
    app.state.interaction_matrix = object()
    app.state.hybrid_transformed = object()

    yield app

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def async_client(unit_app) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=unit_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
