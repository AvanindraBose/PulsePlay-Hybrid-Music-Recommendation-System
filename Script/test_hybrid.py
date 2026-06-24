import pandas as pd
from Script.hybrid_recommendation import HybridRecommenderSystem
from pathlib import Path
from scipy.sparse import load_npz
from numpy import load

ROOT_PATH = Path(__file__).parent.parent
cleaned_data_path = ROOT_PATH / "data" / "cleaned" / "songs-info-collab.csv"
songs_data = pd.read_csv(cleaned_data_path)

transformed_hybrid_data_path = ROOT_PATH / "data" / "processed" / "transformed_hybrid_data.npz"
transformed_hybrid_data = load_npz(transformed_hybrid_data_path)

# load the track ids
track_ids_path = ROOT_PATH / "data" / "processed" / "track_ids.npy"
track_ids = load(track_ids_path,allow_pickle=True)

# load the interaction matrix
interaction_matrix_path = ROOT_PATH / "data" / "processed" / "interaction_matrix.npz"
interaction_matrix = load_npz(interaction_matrix_path)

# load the filtered songs data
filtered_data_path = ROOT_PATH / "data" / "processed" / "collab_filtered.csv"
filtered_data = pd.read_csv(filtered_data_path)

hrs = HybridRecommenderSystem(
    10,0.3
)

df,scores = hrs.give_recommendation(
    song_name="Beat It",
    artist_name="Michael Jackson",
    songs_data=filtered_data,
    transformed_matrix=transformed_hybrid_data,
    track_ids=track_ids,
    interaction_matrix=interaction_matrix
)

track_id = scores.iloc[0]['track_id']
song = filtered_data[
    filtered_data['track_id'] == track_id
]
print("Printing DataFrame",df)
print("Scores DF", scores)
print("song-name",song)