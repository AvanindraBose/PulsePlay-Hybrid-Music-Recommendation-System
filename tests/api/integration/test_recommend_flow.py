async def test_recommendation_search_flow(integration_async_client):
    response = await integration_async_client.get(
        "/api/song/search",
        params={"song_name": "Blinding Lights", "artist_name": "The Weeknd"},
    )

    assert response.status_code == 200
    assert response.json()["found_in_content_db"] is True
    assert response.json()["found_in_collab_db"] is True
