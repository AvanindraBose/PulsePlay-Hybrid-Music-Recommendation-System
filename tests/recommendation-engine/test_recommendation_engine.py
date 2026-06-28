import numpy as np
import pandas as pd
import pytest
from scipy.sparse import csr_matrix

from Script.hybrid_recommendation import HybridRecommenderSystem
from Script.recommender_script import collaborative_recommendation, content_recommendation


@pytest.fixture
def songs_data():
    return pd.DataFrame(
        [
            {"track_id": "t1", "name": "blinding lights", "artist": "the weeknd"},
            {"track_id": "t2", "name": "save your tears", "artist": "the weeknd"},
            {"track_id": "t3", "name": "levitating", "artist": "dua lipa"},
        ]
    )


@pytest.fixture
def feature_matrix():
    return csr_matrix(
        [
            [1.0, 0.0, 0.0],
            [0.9, 0.1, 0.0],
            [0.0, 1.0, 0.0],
        ]
    )


@pytest.fixture
def interaction_matrix():
    return csr_matrix(
        [
            [5.0, 0.0, 1.0],
            [4.0, 0.0, 1.0],
            [0.0, 5.0, 0.0],
        ]
    )


def test_content_recommendation_returns_song_rows(songs_data, feature_matrix):
    result = content_recommendation(
        song_name="Blinding Lights",
        artist_name="The Weeknd",
        songs_data=songs_data,
        transformed_data=feature_matrix,
        k=1,
    )

    assert not result.empty
    assert {"name", "artist"}.issubset(result.columns)


def test_collaborative_recommendation_returns_song_rows(songs_data, interaction_matrix):
    result = collaborative_recommendation(
        song_name="Blinding Lights",
        artist_name="The Weeknd",
        track_ids=np.array(["t1", "t2", "t3"]),
        songs_data=songs_data,
        interaction_matrix=interaction_matrix,
        k=1,
    )

    assert not result.empty
    assert {"name", "artist"}.issubset(result.columns)


def test_recommendation_functions_raise_for_unknown_song(songs_data, feature_matrix):
    with pytest.raises(ValueError, match="Song not found"):
        content_recommendation(
            song_name="Unknown Song",
            artist_name="Unknown Artist",
            songs_data=songs_data,
            transformed_data=feature_matrix,
            k=1,
        )


def test_hybrid_recommender_returns_song_rows(songs_data, feature_matrix, interaction_matrix):
    recommender = HybridRecommenderSystem(
        num_of_recommendations=1,
        weight_content_based=0.5,
    )

    result = recommender.give_recommendation(
        song_name="Blinding Lights",
        artist_name="The Weeknd",
        songs_data=songs_data,
        transformed_matrix=feature_matrix,
        track_ids=np.array(["t1", "t2", "t3"]),
        interaction_matrix=interaction_matrix,
    )

    assert not result.empty
    assert {"name", "artist"}.issubset(result.columns)


def test_hybrid_recommender_validates_weights():
    with pytest.raises(ValueError, match="between 0 and 1"):
        HybridRecommenderSystem(num_of_recommendations=1, weight_content_based=1.5)
