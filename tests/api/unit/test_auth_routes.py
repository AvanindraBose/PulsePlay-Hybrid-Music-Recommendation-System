async def test_signup_page_loads(async_client):
    response = await async_client.get("/auth/signup")

    assert response.status_code == 200
    assert "Create account" in response.text
    assert "Pulse Play" in response.text


async def test_login_page_loads(async_client):
    response = await async_client.get("/auth/login")

    assert response.status_code == 200
    assert "Sign in" in response.text
    assert "Pulse Play" in response.text



async def test_logout_redirects_to_landing(async_client):
    response = await async_client.post("/auth/logout")

    assert response.status_code == 303
    assert response.headers["location"] == "/?logout=success"
