async def test_health_check_loads(integration_async_client):
    response = await integration_async_client.get("/internal/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_public_pages_load(integration_async_client):
    landing_response = await integration_async_client.get("/")
    signup_response = await integration_async_client.get("/auth/signup")
    login_response = await integration_async_client.get("/auth/login")

    assert landing_response.status_code == 200
    assert "Find songs that fit the moment" in landing_response.text

    assert signup_response.status_code == 200
    assert "Create account" in signup_response.text

    assert login_response.status_code == 200
    assert "Sign in" in login_response.text
