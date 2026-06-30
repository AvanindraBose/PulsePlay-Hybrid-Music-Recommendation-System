async def login_test_user(client):
    signup_response = await client.post(
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

    login_response = await client.post(
        "/auth/login",
        data={
            "email": "integration@example.com",
            "password": "StrongPass1!",
        },
        follow_redirects=False,
    )
    assert login_response.status_code == 303
    assert login_response.headers["location"] == "/dashboard"


async def test_recommendation_search_flow(integration_async_client):
    await login_test_user(integration_async_client)

    response = await integration_async_client.get(
        "/api/song/search",
        params={"song_name": "Blinding Lights", "artist_name": "The Weeknd"},
    )

    assert response.status_code == 200
    assert response.json()["found_in_content_db"] is True
    assert response.json()["found_in_collab_db"] is True
