import pandas as pd
import numpy as np
from scipy.sparse import csr_matrix,spmatrix
from backend.logging_fastapi.logger_api import prediction_logger
from sklearn.metrics.pairwise import cosine_similarity
from typing import Union

FeatureMatrix = Union[np.ndarray, spmatrix]

def collaborative_recommendation(
    song_name: str,
    artist_name: str,
    track_ids: np.ndarray,
    songs_data: pd.DataFrame,
    interaction_matrix: csr_matrix,
    k: int = 5,
) -> pd.DataFrame:
    """
    Recommends songs similar to a seed song using collaborative filtering.

    Parameters:
    song_name (str): Name of the seed song.
    artist_name (str): Artist name for the seed song.
    track_ids (np.ndarray): Track IDs aligned with interaction matrix rows.
    songs_data (pd.DataFrame): Filtered songs metadata.
    interaction_matrix (csr_matrix): Track-user playcount interaction matrix.
    k (int): Number of recommendations to return.

    Returns:
    pd.DataFrame: Top k recommended songs.
    """
    try:
        required_cols = {"track_id", "name", "artist"}
        missing_cols = required_cols.difference(songs_data.columns)
        if missing_cols:
            raise ValueError(
                f"songs_data is missing required columns: {sorted(missing_cols)}"
            )

        normalized_song_name = song_name.lower()
        normalized_artist_name = artist_name.lower()

        song_row = songs_data.loc[
            (songs_data["name"].str.lower() == normalized_song_name)
            & (songs_data["artist"].str.lower() == normalized_artist_name)
        ]

        if song_row.empty:
            raise ValueError(
                f"Song not found: '{song_name}' by '{artist_name}'"
            )

        input_track_id = song_row["track_id"].values[0]
        matching_indices = np.where(track_ids == input_track_id)[0]
        if len(matching_indices) == 0:
            raise ValueError(
                f"Track ID not found in interaction matrix: {input_track_id}"
            )

        song_index = matching_indices[0]
        input_array = interaction_matrix[song_index]
        similarity_scores = cosine_similarity(input_array, interaction_matrix)

        recommendation_indices = np.argsort(similarity_scores.ravel())[-k - 1 :][::-1]

        recommendation_track_ids = track_ids[recommendation_indices]
        top_scores = similarity_scores.ravel()[recommendation_indices]

        scores_df = pd.DataFrame(
            {
                "track_id": recommendation_track_ids.tolist(),
                "score": top_scores,
            }
        )

        top_k_songs = (
            songs_data
            .loc[songs_data["track_id"].isin(recommendation_track_ids)]
            .merge(scores_df, on="track_id")
            .sort_values(by="score", ascending=False)
            .drop(columns=["track_id", "score"])
            .reset_index(drop=True)
        )

    except Exception as e:
        prediction_logger.save_logs(
            f"Error generating collaborative recommendations: {str(e)}",
            log_level="error",
        )
        raise

    else:
        prediction_logger.save_logs(
            f"Generated {len(top_k_songs)} collaborative recommendations",
            log_level="info",
        )
        return top_k_songs
    

def content_recommendation(
    song_name: str,
    artist_name: str,
    songs_data: pd.DataFrame,
    transformed_data: FeatureMatrix,
    k: int = 10,
) -> pd.DataFrame:
    """
    Recommends songs similar to a given song using content-based filtering.

    Parameters:
    song_name (str): Name of the song to use as the recommendation seed.
    artist_name (str): Artist name for the seed song.
    songs_data (pd.DataFrame): Song metadata containing at least name and artist.
    transformed_data (FeatureMatrix): Transformed feature matrix for all songs.
    k (int): Number of recommendations to return.

    Returns:
    pd.DataFrame: Top k recommended songs.
    """
    try:
        required_cols = {"name", "artist"}
        missing_cols = required_cols.difference(songs_data.columns)
        if missing_cols:
            raise ValueError(
                f"songs_data is missing required columns: {sorted(missing_cols)}"
            )

        prediction_logger.save_logs(
            f"Generating recommendations for '{song_name}' by '{artist_name}'",
            log_level="info",
        )

        normalized_song_name = song_name.lower()
        normalized_artist_name = artist_name.lower()

        song_row = songs_data.loc[
            (songs_data["name"].str.lower() == normalized_song_name)
            & (songs_data["artist"].str.lower() == normalized_artist_name)
        ]

        if song_row.empty:
            raise ValueError(
                f"Song not found: '{song_name}' by '{artist_name}'"
            )

        song_index = song_row.index[0]
        input_vector = transformed_data[song_index].reshape(1, -1)
        similarity_scores = cosine_similarity(input_vector, transformed_data)

        top_indexes = np.argsort(similarity_scores.ravel())[-k - 1 :][::-1]

        output_cols = [
            col
            for col in ["name", "artist", "pulse_play_preview_url"]
            if col in songs_data.columns
        ]
        recommendations = songs_data.iloc[top_indexes][output_cols].reset_index(drop=True)

    except Exception as e:
        prediction_logger.save_logs(
            f"Error generating content recommendations: {str(e)}",
            log_level="error",
        )
        raise

    else:
        prediction_logger.save_logs(
            f"Generated {len(recommendations)} recommendations",
            log_level="info",
        )
        return recommendations