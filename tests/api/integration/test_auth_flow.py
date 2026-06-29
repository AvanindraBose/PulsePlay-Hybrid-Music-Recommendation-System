from sqlalchemy import select

from backend.core.database import AsyncSessionLocal
from backend.db.refresh_token import RefreshToken
from backend.db.users import User


async def test_dashboard_redirects_to_login_without_session(integration_async_client):
    response = await integration_async_client.get("/dashboard", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/auth/login?session=expired"


async def test_logout_redirects_to_landing(integration_async_client):
    response = await integration_async_client.post("/auth/logout", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/?logout=success"


async def test_signup_login_and_dashboard_flow_uses_real_db_and_redis(integration_async_client):
    signup_response = await integration_async_client.post(
        "/auth/signup",
        data={
            "username": "Integration User",
            "email": "integration@example.com",
            "password": "StrongPass1!",
        },
        follow_redirects=False,
    )

    assert signup_response.status_code == 303
    assert signup_response.headers["location"] == "/auth/login?signup=success"

    async with AsyncSessionLocal() as session:
        user_result = await session.execute(select(User).where(User.email == "integration@example.com"))
        user = user_result.scalar_one_or_none()

    assert user is not None

    login_response = await integration_async_client.post(
        "/auth/login",
        data={
            "email": "integration@example.com",
            "password": "StrongPass1!",
        },
        follow_redirects=False,
    )

    assert login_response.status_code == 303
    assert login_response.headers["location"] == "/dashboard"
    assert "access_token" in integration_async_client.cookies
    assert "refresh_token" in integration_async_client.cookies

    async with AsyncSessionLocal() as session:
        token_result = await session.execute(select(RefreshToken).where(RefreshToken.user_id == user.id))
        refresh_token = token_result.scalar_one_or_none()

    assert refresh_token is not None

    dashboard_response = await integration_async_client.get("/dashboard")

    assert dashboard_response.status_code == 200
    assert "Get recommendations" in dashboard_response.text
    assert "Sign out" in dashboard_response.text
