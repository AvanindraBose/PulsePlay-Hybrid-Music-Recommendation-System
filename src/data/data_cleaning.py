import pandas as pd
import logging
from src.utils.logger import create_log_path, CustomLogger
from datetime import datetime, timezone
from pathlib import Path

log_file_path = create_log_path("Data-Cleaning-Logs")
cleaning_logger = CustomLogger(
    logger_name="Data Cleaning",
    log_filename=log_file_path,
)

cleaning_logger.set_log_level(level=logging.INFO)


def clean_data(data: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans the input DataFrame by performing the following operations:
    1. Removes duplicate rows based on the 'track_id' column.
    2. Drops the 'genre' and 'pulse_play_id' columns.
    3. Fills missing values in the 'tags' column with the string 'no_tags'.
    4. Converts the 'name', 'artist', and 'tags' columns to lowercase.

    Parameters:
    data (pd.DataFrame): The input DataFrame containing the data to be cleaned.

    Returns:
    pd.DataFrame: The cleaned DataFrame.
    """
    try:
        cleaning_logger.save_logs("Starting data cleaning", log_level="info")

        df = data.copy()

        # remove duplicates
        df = df.drop_duplicates(subset="track_id")
        cleaning_logger.save_logs(f"Duplicates removed — {len(df)} rows remaining", log_level="info")

        # drop unnecessary columns
        df = df.drop(columns=["genre", "pulse_play_id"])
        cleaning_logger.save_logs("Dropped columns: genre, pulse_play_id", log_level="info")

        # fill missing values
        df["tags"] = df["tags"].fillna("no_tags")
        cleaning_logger.save_logs("Missing tags filled with 'no_tags'", log_level="info")

        # convert text columns to lowercase
        df["name"] = df["name"].str.lower()
        df["artist"] = df["artist"].str.lower()
        df["tags"] = df["tags"].str.lower()
        cleaning_logger.save_logs("Converted name, artist, tags to lowercase", log_level="info")
        
        df = df.reset_index(drop=True)

        cleaning_logger.save_logs(
            f"Data cleaning complete — {len(df)} rows retained",
            log_level="info"
        )
        return df

    except Exception as e:
        cleaning_logger.save_logs(
            f"Error during data cleaning: {str(e)}",
            log_level="error"
        )
        raise


def data_for_content_filtering(data: pd.DataFrame) -> pd.DataFrame:
    """
    Prepares data for content based filtering by dropping identifier
    and preview columns that are not needed for similarity computation.

    Parameters:
    data (pandas.DataFrame): The input DataFrame containing songs information.

    Returns:
    pandas.DataFrame: A DataFrame with track_id, name, and pulse_play_preview_url removed.
    """
    try:
        cleaning_logger.save_logs(
            "Preparing data for content filtering",
            log_level="info"
        )

        df = data.drop(columns=["track_id", "name", "pulse_play_preview_url"])

        cleaning_logger.save_logs(
            "Content filtering data preparation complete",
            log_level="info"
        )
        return df

    except Exception as e:
        cleaning_logger.save_logs(
            f"Error preparing data for content filtering: {str(e)}",
            log_level="error"
        )
        raise


def load_data(data_path: Path) -> pd.DataFrame:
    try:
        cleaning_logger.save_logs(
            f"Loading data from {data_path}",
            log_level="info"
        )
        df = pd.read_csv(data_path)

    except FileNotFoundError:
        cleaning_logger.save_logs(
            f"File not found: {data_path}",
            log_level="error"
        )
        raise

    except Exception as e:
        cleaning_logger.save_logs(
            f"Unexpected error while loading data: {str(e)}",
            log_level="error"
        )
        raise

    else:
        cleaning_logger.save_logs(
            f"Data loaded successfully — {len(df)} rows, {len(df.columns)} columns",
            log_level="info"
        )
        return df


def save_data(data: pd.DataFrame, output_path: Path) -> None:
    try:
        cleaning_logger.save_logs(
            f"Saving cleaned dataset to: {output_path}",
            log_level="info"
        )
        data.to_csv(output_path, index=False)

    except Exception as e:
        cleaning_logger.save_logs(
            f"Unexpected error while saving data: {str(e)}",
            log_level="error"
        )
        raise

    else:
        cleaning_logger.save_logs(
            f"File saved successfully at: {output_path}",
            log_level="info"
        )


def main():
    """
    Main function to load, clean, and save data.

    Returns:
    None
    """
    try:
        start_time = datetime.now(timezone.utc)
        cleaning_logger.save_logs(
            f"Data Cleaning Pipeline started at {start_time.strftime('%Y-%m-%d %H:%M:%S %Z')}",
            log_level="info",
        )

        root_path = Path(__file__).parent.parent.parent
        data_path = root_path / "data" / "raw" / "songs-info.csv"
        output_path = root_path / "data" / "cleaned"
        cleaned_file_name = "songs-info-cleaned.csv"
        cleaned_collab_file_name = "songs-info-collab.csv"

        output_path.mkdir(exist_ok=True)

        data = load_data(data_path)
        cleaned_data = clean_data(data)
        collab_data = cleaned_data.copy()
        content_cleaned_data = data_for_content_filtering(cleaned_data)
        save_data(content_cleaned_data, output_path / cleaned_file_name)
        save_data(collab_data,output_path / cleaned_collab_file_name)

    except Exception as e:
        cleaning_logger.save_logs(
            f"Pipeline failed: {str(e)}",
            log_level="error"
        )
        raise

    else:
        end_time = datetime.now(timezone.utc)
        cleaning_logger.save_logs(
            f"Data Cleaning Pipeline completed at {end_time.strftime('%Y-%m-%d %H:%M:%S %Z')}",
            log_level="info",
        )


if __name__ == "__main__":
    main()