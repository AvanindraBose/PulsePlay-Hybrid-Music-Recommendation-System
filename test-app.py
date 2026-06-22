from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
from scipy.sparse import load_npz

from Script.hybrid_recommendation import HybridRecommenderSystem
from src.content_based_filtering.content_filtering import content_recommendation
from src.collaborative_filtering.collaborative_recommendation import (
    collaborative_recommendation,
)

ROOT_PATH = Path(__file__).parent
RAW_DATA_PATH = ROOT_PATH / "data" / "cleaned" / "songs-info-collab.csv"
TRANSFORMED_DATA_PATH = (
    ROOT_PATH / "data" / "processed" / "transformed_content_filtering.npz"
)
COLLAB_FILTERED_DATA_PATH = ROOT_PATH / "data" / "processed" / "collab_filtered.csv"
TRACK_IDS_PATH = ROOT_PATH / "data" / "processed" / "track_ids.npy"
INTERACTION_MATRIX_PATH = ROOT_PATH / "data" / "processed" / "interaction_matrix.npz"
HYBRID_TRANSFORMED_DATA_PATH = (
    ROOT_PATH / "data" / "processed" / "transformed_hybrid_data.npz"
)


@st.cache_data
def load_song_metadata(data_path: Path) -> pd.DataFrame:
    """
    Loads song metadata used by the Streamlit recommendation app.

    Parameters:
    data_path (Path): Path to the raw songs dataset.

    Returns:
    pd.DataFrame: Song metadata aligned with the transformed feature matrix.
    """
    data = pd.read_csv(data_path)
    return data


@st.cache_data
def load_collab_song_metadata(data_path: Path) -> pd.DataFrame:
    """
    Loads song metadata aligned with the collaborative filtering artifacts.

    Parameters:
    data_path (Path): Path to the collaborative filtered songs CSV file.

    Returns:
    pd.DataFrame: Filtered song metadata aligned with interaction matrix track IDs.
    """
    data = pd.read_csv(data_path)
    data = data.drop_duplicates(subset="track_id").reset_index(drop=True)
    data["name"] = data["name"].str.lower()
    data["artist"] = data["artist"].str.lower()
    return data


@st.cache_resource
def load_transformed_data(data_path: Path):
    """
    Loads the transformed feature matrix used for similarity search.

    Parameters:
    data_path (Path): Path to the saved sparse NPZ feature matrix.

    Returns:
    scipy.sparse.spmatrix: Transformed song feature matrix.
    """
    return load_npz(data_path)


@st.cache_data
def load_track_ids(data_path: Path):
    """
    Loads track IDs aligned with the collaborative interaction matrix rows.

    Parameters:
    data_path (Path): Path to the saved NPY track IDs file.

    Returns:
    np.ndarray: Track IDs in interaction matrix row order.
    """
    return np.load(data_path, allow_pickle=True)


@st.cache_resource
def load_interaction_matrix(data_path: Path):
    """
    Loads the collaborative filtering interaction matrix.

    Parameters:
    data_path (Path): Path to the saved sparse NPZ interaction matrix.

    Returns:
    scipy.sparse.spmatrix: Track-user interaction matrix.
    """
    return load_npz(data_path)


def format_label(row: pd.Series) -> str:
    """
    Formats a song row for display in Streamlit selection widgets.

    Parameters:
    row (pd.Series): Song metadata row containing name and artist.

    Returns:
    str: Human-readable song and artist label.
    """
    return f"{row['name'].title()} - {row['artist'].title()}"


def main() -> None:
    """
    Runs the Streamlit hybrid music recommender app.

    Returns:
    None
    """
    st.set_page_config(
        page_title="Pulse Play Song Recommender",
        layout="centered",
    )

    st.title("Pulse Play Song Recommender")
    st.write("Choose a song and get similar tracks based on audio and tag features.")

    if not RAW_DATA_PATH.exists():
        st.error(f"Raw songs file not found: {RAW_DATA_PATH}")
        st.stop()

    filtering_type = st.selectbox(
        "Recommendation type",
        options=[
            "Content-Based Filtering",
            "Collaborative Filtering",
            "Hybrid Recommendation",
        ],
    )

    if (
        filtering_type == "Content-Based Filtering"
        and not TRANSFORMED_DATA_PATH.exists()
    ):
        st.error(
            "Transformed feature file not found. Run the content filtering pipeline first."
        )
        st.code(
            ".\\.venv\\Scripts\\python.exe src\\content_based_filtering\\content_filtering.py",
            language="powershell",
        )
        st.stop()

    collab_paths = [
        COLLAB_FILTERED_DATA_PATH,
        TRACK_IDS_PATH,
        INTERACTION_MATRIX_PATH,
    ]
    missing_collab_paths = [path for path in collab_paths if not path.exists()]
    hybrid_paths = [
        COLLAB_FILTERED_DATA_PATH,
        TRACK_IDS_PATH,
        INTERACTION_MATRIX_PATH,
        HYBRID_TRANSFORMED_DATA_PATH,
    ]
    missing_hybrid_paths = [path for path in hybrid_paths if not path.exists()]

    if filtering_type == "Collaborative Filtering" and missing_collab_paths:
        st.error(
            "Collaborative filtering files were not found. "
            "Run the collaborative filtering pipeline first."
        )
        for path in missing_collab_paths:
            st.code(str(path))
        st.stop()

    if filtering_type == "Hybrid Recommendation" and missing_hybrid_paths:
        st.error(
            "Hybrid recommendation files were not found. "
            "Run the collaborative filtering and transform-filtered-data pipelines first."
        )
        for path in missing_hybrid_paths:
            st.code(str(path))
        st.stop()

    if filtering_type == "Content-Based Filtering":
        songs_data = load_song_metadata(RAW_DATA_PATH)
        transformed_data = load_transformed_data(TRANSFORMED_DATA_PATH)

        if len(songs_data) != transformed_data.shape[0]:
            st.error(
                "Song metadata and transformed feature matrix are not aligned. "
                "Re-run the data cleaning and content filtering pipelines."
            )
            st.stop()

    elif filtering_type == "Collaborative Filtering":
        songs_data = load_collab_song_metadata(COLLAB_FILTERED_DATA_PATH)
        track_ids = load_track_ids(TRACK_IDS_PATH)
        interaction_matrix = load_interaction_matrix(INTERACTION_MATRIX_PATH)

        if interaction_matrix.shape[0] != len(track_ids):
            st.error(
                "Track IDs and interaction matrix are not aligned. "
                "Re-run the collaborative filtering pipeline."
            )
            st.stop()

    else:
        songs_data = load_collab_song_metadata(COLLAB_FILTERED_DATA_PATH)
        transformed_data = load_transformed_data(HYBRID_TRANSFORMED_DATA_PATH)
        track_ids = load_track_ids(TRACK_IDS_PATH)
        interaction_matrix = load_interaction_matrix(INTERACTION_MATRIX_PATH)

        if len(songs_data) != transformed_data.shape[0]:
            st.error(
                "Filtered songs data and transformed hybrid matrix are not aligned. "
                "Re-run the transform-filtered-data pipeline."
            )
            st.stop()

        if interaction_matrix.shape[0] != len(track_ids):
            st.error(
                "Track IDs and interaction matrix are not aligned. "
                "Re-run the collaborative filtering pipeline."
            )
            st.stop()

    song_options = songs_data[["name", "artist"]].drop_duplicates().sort_values(
        by=["name", "artist"]
    )
    selected_label = st.selectbox(
        "Select a song",
        options=song_options.index,
        format_func=lambda index: format_label(song_options.loc[index]),
    )
    selected_song = song_options.loc[selected_label]

    k = st.selectbox(
        "Number of recommendations",
        options=[5, 10, 15, 20],
        index=1,
    )

    content_weight = 0.5
    if filtering_type == "Hybrid Recommendation":
        content_weight = st.slider(
            "Content-based weight",
            min_value=0.0,
            max_value=1.0,
            value=0.5,
            step=0.05,
        )

    if st.button("Get Recommendations", type="primary"):
        try:
            if filtering_type == "Content-Based Filtering":
                recommendations = content_recommendation(
                    song_name=selected_song["name"],
                    artist_name=selected_song["artist"],
                    songs_data=songs_data,
                    transformed_data=transformed_data,
                    k=k,
                )

            elif filtering_type == "Collaborative Filtering":
                recommendations = collaborative_recommendation(
                    song_name=selected_song["name"],
                    artist_name=selected_song["artist"],
                    track_ids=track_ids,
                    songs_data=songs_data,
                    interaction_matrix=interaction_matrix,
                    k=k,
                )

            else:
                recommender = HybridRecommenderSystem(
                    num_of_recommendations=k,
                    weight_content_based=content_weight,
                )
                recommendations = recommender.give_recommendation(
                    song_name=selected_song["name"],
                    artist_name=selected_song["artist"],
                    songs_data=songs_data,
                    transformed_matrix=transformed_data,
                    track_ids=track_ids,
                    interaction_matrix=interaction_matrix,
                )

        except ValueError as e:
            st.warning(str(e))

        except Exception as e:
            st.error(f"Unable to generate recommendations: {str(e)}")

        else:
            st.subheader(
                f"{filtering_type} recommendations for "
                f"{selected_song['name'].title()} by {selected_song['artist'].title()}"
            )

            for index, recommendation in recommendations.iterrows():

                song_name = recommendation["name"].title()
                artist_name = recommendation["artist"].title()

                # Header
                if index == 0:
                    st.markdown("## Currently Playing")
                    st.markdown(f"#### **{song_name}** by **{artist_name}**")

                elif index == 1:
                    st.markdown("### Next Up 🎵")
                    st.markdown(f"#### {index}. **{song_name}** by **{artist_name}**")

                else:
                    st.markdown(f"#### {index}. **{song_name}** by **{artist_name}**")

                # Preview URL
                preview_url = recommendation.get("pulse_play_preview_url")

                # Fall back to spotify preview if pulse play preview is unavailable
                if pd.isna(preview_url) or not preview_url:
                    preview_url = recommendation.get("spotify_preview_url")

                if pd.notna(preview_url) and preview_url:
                    st.audio(preview_url)
                else:
                    st.caption("Preview audio is not available for this track.")

                st.divider()


if __name__ == "__main__":
    main()