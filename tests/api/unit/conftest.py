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
    async def ping(self) -> bool:
        return True


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

    app.dependency_overrides[dependencies.get_db] = override_get_db
    app.dependency_overrides[dependencies.get_redis_client] = override_get_redis

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
