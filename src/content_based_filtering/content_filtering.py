import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Union

import joblib
import numpy as np
import pandas as pd
from category_encoders.count import CountEncoder
from scipy.sparse import csr_matrix, issparse, save_npz, spmatrix
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MinMaxScaler, OneHotEncoder, StandardScaler

from src.utils.logger import CustomLogger, create_log_path

log_file_path = create_log_path("Content-Filtering-Logs")
content_logger = CustomLogger(
    logger_name="Content Filtering",
    log_filename=log_file_path,
)

content_logger.set_log_level(level=logging.INFO)

frequency_encode_cols = ["year"]
ohe_cols = ["artist", "time_signature", "key"]
tfidf_col = "tags"
standard_scale_cols = ["duration_ms", "loudness", "tempo"]
min_max_scale_cols = [
    "danceability",
    "energy",
    "speechiness",
    "acousticness",
    "instrumentalness",
    "liveness",
    "valence",
]

FeatureMatrix = Union[np.ndarray, spmatrix]


def load_data(data_path: Path) -> pd.DataFrame:
    """
    Loads the cleaned songs dataset from the provided CSV path.

    Parameters:
    data_path (Path): Path to the cleaned songs CSV file.

    Returns:
    pd.DataFrame: Loaded songs data.
    """
    try:
        content_logger.save_logs(
            f"Loading data from {data_path}",
            log_level="info",
        )
        df = pd.read_csv(data_path)

    except FileNotFoundError:
        content_logger.save_logs(
            f"File not found: {data_path}",
            log_level="error",
        )
        raise

    except Exception as e:
        content_logger.save_logs(
            f"Unexpected error while loading data: {str(e)}",
            log_level="error",
        )
        raise

    else:
        content_logger.save_logs(
            f"Data loaded successfully - {len(df)} rows, {len(df.columns)} columns",
            log_level="info",
        )
        return df


def make_transformer() -> ColumnTransformer:
    """
    Builds the preprocessing transformer used for content-based filtering.

    Returns:
    ColumnTransformer: Transformer that encodes categorical/text features and
    scales numerical features.
    """
    try:
        content_logger.save_logs(
            "Creating content filtering transformer",
            log_level="info",
        )

        transformer = ColumnTransformer(
            transformers=[
                (
                    "frequency_encode",
                    CountEncoder(
                        cols=frequency_encode_cols,
                        normalize=True,
                        return_df=True,
                    ),
                    frequency_encode_cols,
                ),
                ("one_hot_encode", OneHotEncoder(handle_unknown="ignore"), ohe_cols),
                ("tfidf", TfidfVectorizer(max_features=85), tfidf_col),
                ("standard_scale", StandardScaler(), standard_scale_cols),
                ("min_max_scale", MinMaxScaler(), min_max_scale_cols),
            ],
            remainder="passthrough",
            n_jobs=-1,
        )

    except Exception as e:
        content_logger.save_logs(
            f"Error creating content filtering transformer: {str(e)}",
            log_level="error",
        )
        raise

    else:
        content_logger.save_logs(
            "Content filtering transformer created successfully",
            log_level="info",
        )
        return transformer


def train_transformer(
    transformer: ColumnTransformer,
    data: pd.DataFrame,
    save_transformer_path: Path,
) -> None:
    """
    Fits the preprocessing transformer on the songs data and saves it to disk.

    Parameters:
    transformer (ColumnTransformer): Transformer to fit.
    data (pd.DataFrame): Songs data used for fitting.
    save_transformer_path (Path): Path where the fitted transformer is saved.

    Returns:
    None
    """
    try:
        content_logger.save_logs(
            "Starting transformer training",
            log_level="info",
        )

        transformer.fit(data)
        joblib.dump(transformer, save_transformer_path)

    except Exception as e:
        content_logger.save_logs(
            f"Unexpected error during transformer training: {str(e)}",
            log_level="error",
        )
        raise

    else:
        content_logger.save_logs(
            f"Transformer trained and saved at: {save_transformer_path}",
            log_level="info",
        )


def transform_data(data: pd.DataFrame, transformer_path: Path) -> FeatureMatrix:
    """
    Transforms songs data using a saved fitted transformer.

    Parameters:
    data (pd.DataFrame): Songs data to transform.
    transformer_path (Path): Path to the saved fitted transformer.

    Returns:
    FeatureMatrix: Transformed feature matrix.
    """
    try:
        content_logger.save_logs(
            f"Loading transformer from {transformer_path}",
            log_level="info",
        )
        transformer: ColumnTransformer = joblib.load(transformer_path)

        content_logger.save_logs(
            "Starting data transformation",
            log_level="info",
        )
        transformed_data = transformer.transform(data)

    except FileNotFoundError:
        content_logger.save_logs(
            f"Transformer file not found: {transformer_path}",
            log_level="error",
        )
        raise

    except Exception as e:
        content_logger.save_logs(
            f"Error during data transformation: {str(e)}",
            log_level="error",
        )
        raise

    else:
        content_logger.save_logs(
            f"Data transformation complete - output shape: {transformed_data.shape}",
            log_level="info",
        )
        return transformed_data


def calculate_similarity_scores(
    input_vector: FeatureMatrix,
    data: FeatureMatrix,
) -> np.ndarray:
    """
    Calculates cosine similarity scores between one song vector and all songs.

    Parameters:
    input_vector (FeatureMatrix): Feature vector for the selected song.
    data (FeatureMatrix): Transformed feature matrix for all songs.

    Returns:
    np.ndarray: Similarity scores for each song.
    """
    try:
        content_logger.save_logs(
            "Calculating cosine similarity scores",
            log_level="info",
        )
        similarity_scores = cosine_similarity(input_vector, data)

    except Exception as e:
        content_logger.save_logs(
            f"Error calculating similarity scores: {str(e)}",
            log_level="error",
        )
        raise

    else:
        content_logger.save_logs(
            "Similarity scores calculated successfully",
            log_level="info",
        )
        return similarity_scores


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

        content_logger.save_logs(
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
        similarity_scores = calculate_similarity_scores(input_vector, transformed_data)

        top_indexes = np.argsort(similarity_scores.ravel())[-k - 1 :][::-1]
        top_indexes = [index for index in top_indexes if index != song_index][:k]

        output_cols = [
            col
            for col in ["name", "artist", "pulse_play_preview_url"]
            if col in songs_data.columns
        ]
        recommendations = songs_data.iloc[top_indexes][output_cols].reset_index(drop=True)

    except Exception as e:
        content_logger.save_logs(
            f"Error generating content recommendations: {str(e)}",
            log_level="error",
        )
        raise

    else:
        content_logger.save_logs(
            f"Generated {len(recommendations)} recommendations",
            log_level="info",
        )
        return recommendations


def save_transformed_data(transformed_data: FeatureMatrix, save_path: Path) -> None:
    """
    Saves the transformed feature matrix as a sparse NPZ file.

    Parameters:
    transformed_data (FeatureMatrix): Transformed feature matrix to save.
    save_path (Path): Output path for the NPZ file.

    Returns:
    None
    """
    try:
        content_logger.save_logs(
            f"Saving transformed data to: {save_path}",
            log_level="info",
        )

        sparse_data = (
            transformed_data
            if issparse(transformed_data)
            else csr_matrix(transformed_data)
        )
        save_npz(save_path, sparse_data)

    except Exception as e:
        content_logger.save_logs(
            f"Unexpected error while saving transformed data: {str(e)}",
            log_level="error",
        )
        raise

    else:
        content_logger.save_logs(
            f"Transformed data saved successfully at: {save_path}",
            log_level="info",
        )


def main() -> None:
    """
    Runs the content filtering pipeline.

    Returns:
    None
    """
    try:
        start_time = datetime.now(timezone.utc)
        content_logger.save_logs(
            f"Content Filtering Pipeline started at {start_time.strftime('%Y-%m-%d %H:%M:%S %Z')}",
            log_level="info",
        )

        root_path = Path(__file__).parent.parent.parent
        data_path = root_path / "data" / "cleaned" / "songs-info-cleaned.csv"
        transformed_data_path = root_path / "data" / "processed"
        transformed_data_name = "transformed_content_filtering.npz"
        transformer_path = root_path / "models"
        transformer_name = "transformers.joblib"

        transformer_path.mkdir(exist_ok=True)
        transformed_data_path.mkdir(exist_ok=True)

        df = load_data(data_path)
        transformer = make_transformer()
        train_transformer(transformer, df, transformer_path / transformer_name)

        transformed_data = transform_data(df, transformer_path / transformer_name)
        save_transformed_data(
            transformed_data,
            transformed_data_path / transformed_data_name,
        )

    except Exception as e:
        content_logger.save_logs(
            f"Content Filtering Pipeline failed: {str(e)}",
            log_level="error",
        )
        raise

    else:
        end_time = datetime.now(timezone.utc)
        content_logger.save_logs(
            f"Content Filtering Pipeline completed at {end_time.strftime('%Y-%m-%d %H:%M:%S %Z')}",
            log_level="info",
        )


if __name__ == "__main__":
    main()
