from pathlib import Path

import pandas as pd
import streamlit as st
from scipy.sparse import load_npz

from src.content_based_filtering.content_filtering import content_recommendation

ROOT_PATH = Path(__file__).parent
RAW_DATA_PATH = ROOT_PATH / "data" / "raw" / "songs-info.csv"
TRANSFORMED_DATA_PATH = (
    ROOT_PATH / "data" / "processed" / "transformed_content_filtering.npz"
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
    Runs the Streamlit content-based music recommender app.

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

    if not TRANSFORMED_DATA_PATH.exists():
        st.error(
            "Transformed feature file not found. Run the content filtering pipeline first."
        )
        st.code(
            ".\\.venv\\Scripts\\python.exe src\\content_based_filtering\\content_filtering.py",
            language="powershell",
        )
        st.stop()

    songs_data = load_song_metadata(RAW_DATA_PATH)
    transformed_data = load_transformed_data(TRANSFORMED_DATA_PATH)

    if len(songs_data) != transformed_data.shape[0]:
        st.error(
            "Song metadata and transformed feature matrix are not aligned. "
            "Re-run the data cleaning and content filtering pipelines."
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

    if st.button("Get Recommendations", type="primary"):
        try:
            recommendations = content_recommendation(
                song_name=selected_song["name"],
                artist_name=selected_song["artist"],
                songs_data=songs_data,
                transformed_data=transformed_data,
                k=k,
            )

        except ValueError as e:
            st.warning(str(e))

        except Exception as e:
            st.error(f"Unable to generate recommendations: {str(e)}")

        else:
            st.subheader(
                f"Similar to {selected_song['name'].title()} by {selected_song['artist'].title()}"
            )

            for index, recommendation in recommendations.iterrows():
                song_name = recommendation["name"].title()
                artist_name = recommendation["artist"].title()

                st.markdown(f"**{index + 1}. {song_name}** by **{artist_name}**")

                preview_url = recommendation.get("pulse_play_preview_url")
                if pd.notna(preview_url) and preview_url:
                    st.audio(preview_url)
                else:
                    st.caption("Preview audio is not available for this track.")

                st.divider()


if __name__ == "__main__":
    main()
