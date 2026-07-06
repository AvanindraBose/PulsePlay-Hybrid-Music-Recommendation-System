import pandas as pd
import logging
import dask.dataframe as dd
from scipy.sparse import csr_matrix, save_npz
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from src.utils.logger import CustomLogger, create_log_path
from datetime import datetime, timezone
from pathlib import Path

log_file_path = create_log_path("Collaborative-Filtering-Logs")
collab_logger = CustomLogger(
    logger_name="Collaborative Filtering",
    log_filename=log_file_path,
)

collab_logger.set_log_level(level=logging.INFO)


def filter_songs_data(songs_data: pd.DataFrame, track_ids: list, save_df_path: str) -> pd.DataFrame:
    """
    Filters songs metadata to tracks present in the user listening history.

    Parameters:
    songs_data (pd.DataFrame): Cleaned songs metadata.
    track_ids (list): Track IDs found in the listening history.
    save_df_path (str): CSV path where the filtered metadata is saved.

    Returns:
    pd.DataFrame: Filtered songs metadata reset to a contiguous index.
    """
    try:
        collab_logger.save_logs("Filtering Songs Data based on unique Track Id's ",log_level="info")
        filtered_data = songs_data[songs_data["track_id"].isin(track_ids)].copy()
        filtered_data.reset_index(drop=True, inplace=True)
        # save the data
        save_pandas_data_to_csv(filtered_data, save_df_path)

    except Exception as e :
        collab_logger.save_logs(f"Unable to filter Songs Dataset due to: {str(e)}",log_level="error")
        raise

    else :
        collab_logger.save_logs("Data Filtered Successfully on Unique Track Id's",log_level="info")

        return filtered_data


def save_pandas_data_to_csv(data: pd.DataFrame, file_path: str) -> None:
    """
    Saves a pandas DataFrame to a CSV file.

    Parameters:
    data (pd.DataFrame): DataFrame to save.
    file_path (str): Output CSV path.

    Returns:
    None
    """
    try:
        collab_logger.save_logs("Saving Dataset.",log_level="info")
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        data.to_csv(file_path, index=False)
    
    except Exception as e :
        collab_logger.save_logs(f"Unable to Save Dataset in the given path:{file_path} due to: {str(e)}",log_level="error")
        raise

    else :
        collab_logger.save_logs(f"Successfully saved Datase to the path:{file_path}",log_level="info")
    
    
def save_sparse_matrix(matrix: csr_matrix, file_path: str) -> None:
    """
    Saves a scipy sparse matrix to an NPZ file.

    Parameters:
    matrix (csr_matrix): Sparse interaction matrix to save.
    file_path (str): Output NPZ path.

    Returns:
    None
    """
    try:
        collab_logger.save_logs("Saving Sparse Matrix",log_level="info")

        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        save_npz(file_path, matrix)
    
    except Exception as e:

        collab_logger.save_logs(f"Unable to save matrix in the path: {file_path} due to: {str(e)}",log_level="error")
        raise

    else:
        collab_logger.save_logs(f"Successfully Saved Sparse Matrix in the path: {file_path}",log_level="info")


def create_interaction_matrix(
    history_data: dd.DataFrame,
    track_ids_save_path: Path,
    save_matrix_path: Path,
) -> None:
    """
    Creates and saves the track-user playcount interaction matrix.

    Parameters:
    history_data (dd.DataFrame): User listening history with user_id, track_id,
    and playcount columns.
    track_ids_save_path (Path): Output path for track ID categories as NPY.
    save_matrix_path (Path): Output path for the sparse interaction matrix.

    Returns:
    None
    """
    try:
        required_cols = {"user_id", "track_id", "playcount"}
        missing_cols = required_cols.difference(history_data.columns)
        if missing_cols:
            raise ValueError(
                f"history_data is missing required columns: {sorted(missing_cols)}"
            )

        # Doing the Same Steps as Done in Notebooks
        # make a copy of data
        df = history_data.copy()
        
        # convert the playcount column to float
        df['playcount'] = df['playcount'].astype(np.float64)
        
        # convert string column to categorical
        df = df.categorize(columns=['user_id', 'track_id'])
        
        # Convert user_id and track_id to numeric indices
        user_mapping = df['user_id'].cat.codes
        track_mapping = df['track_id'].cat.codes
        
        # get the list of track_ids
        track_ids = df['track_id'].cat.categories.values
        user_ids = df['user_id'].cat.categories.values
        
        # save the categories
        Path(track_ids_save_path).parent.mkdir(parents=True, exist_ok=True)
        np.save(track_ids_save_path, track_ids, allow_pickle=True)
        
        # add the index columns to the dataframe
        df = df.assign(
            user_idx=user_mapping,
            track_idx=track_mapping
        )
        
        # create the interaction matrix
        interaction_matrix = df.groupby(['track_idx', 'user_idx'])['playcount'].sum().reset_index()
        
        # compute the matrix
        interaction_matrix = interaction_matrix.compute()
        
        # get the indices to form sparse matrix
        row_indices = interaction_matrix['track_idx']
        col_indices = interaction_matrix['user_idx']
        values = interaction_matrix['playcount']
        
        # get the shape of sparse matrix
        n_tracks = len(track_ids)
        n_users = len(user_ids)
        
        # create the sparse matrix
        interaction_matrix = csr_matrix((values, (row_indices, col_indices)), shape=(n_tracks, n_users))
        
        # save the sparse matrix
        save_sparse_matrix(interaction_matrix, save_matrix_path)
    
    except Exception as e:
        collab_logger.save_logs(f"Error While Creating and Saving Sparse Matrix: {str(e)}",log_level="error")
        raise

    else:
        collab_logger.save_logs(f"Successfully Created and Saved Sparse Matrix",log_level="info")
    

def get_unique_track_ids(df:dd.DataFrame) -> list:
    """
    Fetches unique track IDs from a Dask listening history DataFrame.

    Parameters:
    df (dd.DataFrame): User listening history containing a track_id column.

    Returns:
    list: Unique track IDs found in the listening history.
    """
    try:
        collab_logger.save_logs("Fetching Unique Track Id's",log_level='info')
        unique_track_ids = df.loc[:,"track_id"].unique().compute()
        unique_track_ids = unique_track_ids.to_list()
    except Exception as e:
        collab_logger.save_logs("Error While Fetching Unique Track Id's ",log_level="error")
        raise
    else:
        collab_logger.save_logs("Fetched Unique Track Id's",log_level="info")
        return unique_track_ids
    

def load_songs_cleaned_data(data_path: Path) -> pd.DataFrame:
    """
    Loads the cleaned songs dataset from the provided CSV path.

    Parameters:
    data_path (Path): Path to the cleaned songs CSV file.

    Returns:
    pd.DataFrame: Loaded songs data.
    """
    try:
        collab_logger.save_logs(
            f"Loading data from {data_path}",
            log_level="info",
        )
        df = pd.read_csv(data_path)

    except FileNotFoundError:
        collab_logger.save_logs(
            f"File not found: {data_path}",
            log_level="error",
        )
        raise

    except Exception as e:
        collab_logger.save_logs(
            f"Unexpected error while loading data: {str(e)}",
            log_level="error",
        )
        raise

    else:
        collab_logger.save_logs(
            f"Data loaded successfully - {len(df)} rows, {len(df.columns)} columns",
            log_level="info",
        )
        return df


def load_user_data(user_listening_history_data_path: Path) -> dd.DataFrame:
    """
    Loads the User Listening History dataset from the provided CSV path.

    Parameters:
    user_listening_history_data_path (Path): Path to the listening history CSV file.

    Returns:
    dd.DataFrame: Loaded user listening history data.
    """
    try:
        collab_logger.save_logs(
            f"Loading data from {user_listening_history_data_path}",
            log_level="info",
        )
        
        df = dd.read_csv(user_listening_history_data_path)

    except FileNotFoundError:
        collab_logger.save_logs(
            f"File not found: {user_listening_history_data_path}",
            log_level="error",
        )
        raise

    except Exception as e:
        collab_logger.save_logs(
            f"Unexpected error while loading data: {str(e)}",
            log_level="error",
        )
        raise

    else:
        collab_logger.save_logs(
            f"Data loaded successfully - {len(df)} rows, {len(df.columns)} columns",
            log_level="info",
        )
        return df


def main() -> None:
    """
    Runs the collaborative filtering artifact generation pipeline.

    Returns:
    None
    """
    try: 
        start_time = datetime.now(timezone.utc)
        collab_logger.save_logs(
            f"Collaborative Filtering Pipeline started at {start_time.strftime('%Y-%m-%d %H:%M:%S %Z')}",
            log_level="info",
        )
    # load the history data
        root_path = Path(__file__).parent.parent.parent
        user_listening_history_data_path = root_path / "data" / "raw" / "user-info.csv"
        songs_data_path = root_path / "data" / "cleaned" / "songs-info-collab.csv"
        filtered_data_save_path = root_path / "data" / "processed"
        filtered_data_name = "collab_filtered.csv"
        track_ids_save_path = root_path / "data" / "processed"
        track_ids_file_name = "track_ids.npy"
        interaction_matrix_save_path = root_path / "data" / "processed"
        interaction_matrix_file_name = "interaction_matrix.npz"

        filtered_data_save_path.mkdir(parents=True, exist_ok=True)
        track_ids_save_path.mkdir(parents=True, exist_ok=True)
        interaction_matrix_save_path.mkdir(parents=True, exist_ok=True)

        # get the data
        user_data = load_user_data(user_listening_history_data_path)
        
        # get the unique track ids
        unique_track_ids = get_unique_track_ids(user_data)
        
        # filter the songs data
        songs_data = load_songs_cleaned_data(songs_data_path)
        filter_songs_data(songs_data, unique_track_ids, filtered_data_save_path/filtered_data_name)
        
        # create the interaction matrix
        create_interaction_matrix(user_data, track_ids_save_path / track_ids_file_name, interaction_matrix_save_path / interaction_matrix_file_name)
    
    except Exception as e:
        collab_logger.save_logs(
            f"Collaborative Filtering Pipeline failed: {str(e)}",
            log_level="error",
        )
        raise

    else:
        end_time = datetime.now(timezone.utc)
        collab_logger.save_logs(
            f"Collaborative Filtering Pipeline completed at {end_time.strftime('%Y-%m-%d %H:%M:%S %Z')}",
            log_level="info",
        )


if __name__ == "__main__":
    main()
