async def test_dashboard_redirects_to_login_without_session(integration_async_client):
    response = await integration_async_client.get("/dashboard", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/auth/login?session=expired"


async def test_logout_redirects_to_landing(integration_async_client):
    response = await integration_async_client.post("/auth/logout", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/?logout=success"
