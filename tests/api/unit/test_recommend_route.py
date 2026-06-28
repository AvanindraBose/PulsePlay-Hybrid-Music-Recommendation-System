import pandas as pd

from backend.api import routes_recommendation


async def test_song_search_returns_available_recommenders(async_client):
    response = await async_client.get(
        "/api/song/search",
        params={"song_name": "Blinding Lights", "artist_name": "The Weeknd"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "song_name": "Blinding Lights",
        "artist_name": "The Weeknd",
        "found_in_content_db": True,
        "found_in_collab_db": True,
    }


async def test_song_search_returns_404_for_unknown_song(async_client):
    response = await async_client.get(
        "/api/song/search",
        params={"song_name": "Unknown", "artist_name": "Nobody"},
    )

    assert response.status_code == 404
    assert "was not found" in response.json()["detail"]


async def test_content_recommendation_returns_songs(async_client, monkeypatch):
    def fake_content_recommendation(**_kwargs):
        return pd.DataFrame(
            [
                {
                    "name": "save your tears",
                    "artist": "the weeknd",
                    "pulse_play_preview_url": "https://example.com/preview.mp3",
                }
            ]
        )

    monkeypatch.setattr(routes_recommendation, "content_recommendation", fake_content_recommendation)

    response = await async_client.post(
        "/api/recommend/content",
        json={"song_name": "Blinding Lights", "artist_name": "The Weeknd", "k": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["filter_type"] == "Content-Based Filtering"
    assert body["recommendations"] == [
        {
            "song_name": "Save Your Tears",
            "artist_name": "The Weeknd",
            "pulse_play_preview_url": "https://example.com/preview.mp3",
        }
    ]
