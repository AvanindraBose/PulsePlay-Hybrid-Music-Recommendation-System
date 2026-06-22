import logging
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from src.content_based_filtering.content_filtering import (
    FeatureMatrix,
    save_transformed_data,
    transform_data,
)
from src.data.data_cleaning import data_for_content_filtering
from src.utils.logger import CustomLogger, create_log_path

log_file_path = create_log_path("Transform-Filtered-Logs")
transform_filter_logger = CustomLogger(
    logger_name="Transform Filtered Data",
    log_filename=log_file_path,
)

transform_filter_logger.set_log_level(level=logging.INFO)


def load_filtered_data(data_path: Path) -> pd.DataFrame:
    """
    Loads the collaborative-filtered songs dataset from disk.

    Parameters:
    data_path (Path): Path to the collaborative-filtered songs CSV file.

    Returns:
    pd.DataFrame: Loaded collaborative-filtered songs data.
    """
    try:
        transform_filter_logger.save_logs(
            f"Loading filtered data from {data_path}",
            log_level="info",
        )
        df = pd.read_csv(data_path)

    except FileNotFoundError:
        transform_filter_logger.save_logs(
            f"Filtered data file not found: {data_path}",
            log_level="error",
        )
        raise

    except Exception as e:
        transform_filter_logger.save_logs(
            f"Unexpected error while loading filtered data: {str(e)}",
            log_level="error",
        )
        raise

    else:
        transform_filter_logger.save_logs(
            f"Filtered data loaded successfully - {len(df)} rows, {len(df.columns)} columns",
            log_level="info",
        )
        return df


def prepare_filtered_data(data: pd.DataFrame) -> pd.DataFrame:
    """
    Prepares collaborative-filtered songs for the saved content transformer.

    Parameters:
    data (pd.DataFrame): Collaborative-filtered songs data with metadata columns.

    Returns:
    pd.DataFrame: Feature-only data ready for transformation.
    """
    try:
        required_cols = {"track_id", "name", "pulse_play_preview_url"}
        missing_cols = required_cols.difference(data.columns)
        if missing_cols:
            raise ValueError(
                f"Filtered data is missing required columns: {sorted(missing_cols)}"
            )

        transform_filter_logger.save_logs(
            "Preparing filtered data for content transformer",
            log_level="info",
        )
        prepared_data = data_for_content_filtering(data)

    except Exception as e:
        transform_filter_logger.save_logs(
            f"Error preparing filtered data: {str(e)}",
            log_level="error",
        )
        raise

    else:
        transform_filter_logger.save_logs(
            "Filtered data prepared successfully",
            log_level="info",
        )
        return prepared_data


def transform_filtered_data(
    filtered_data: pd.DataFrame,
    transformer_path: Path,
) -> FeatureMatrix:
    """
    Transforms prepared collaborative-filtered songs with the fitted transformer.

    Parameters:
    filtered_data (pd.DataFrame): Feature-only collaborative-filtered songs data.
    transformer_path (Path): Path to the fitted content transformer artifact.

    Returns:
    FeatureMatrix: Transformed hybrid feature matrix.
    """
    try:
        transform_filter_logger.save_logs(
            f"Transforming filtered data using transformer: {transformer_path}",
            log_level="info",
        )
        transformed_data = transform_data(filtered_data, transformer_path)

    except Exception as e:
        transform_filter_logger.save_logs(
            f"Error transforming filtered data: {str(e)}",
            log_level="error",
        )
        raise

    else:
        transform_filter_logger.save_logs(
            f"Filtered data transformed successfully - output shape: {transformed_data.shape}",
            log_level="info",
        )
        return transformed_data


def save_hybrid_transformed_data(
    transformed_data: FeatureMatrix,
    save_path: Path,
) -> None:
    """
    Saves the transformed hybrid feature matrix to disk.

    Parameters:
    transformed_data (FeatureMatrix): Transformed hybrid feature matrix.
    save_path (Path): Output NPZ path for the transformed hybrid matrix.

    Returns:
    None
    """
    try:
        transform_filter_logger.save_logs(
            f"Saving transformed hybrid data to {save_path}",
            log_level="info",
        )
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_transformed_data(transformed_data, save_path)

    except Exception as e:
        transform_filter_logger.save_logs(
            f"Error saving transformed hybrid data: {str(e)}",
            log_level="error",
        )
        raise

    else:
        transform_filter_logger.save_logs(
            f"Transformed hybrid data saved successfully at {save_path}",
            log_level="info",
        )


def main() -> None:
    """
    Runs the filtered-data transformation pipeline for hybrid recommendations.

    Returns:
    None
    """
    try:
        start_time = datetime.now(timezone.utc)
        transform_filter_logger.save_logs(
            f"Transform Filtered Data Pipeline started at {start_time.strftime('%Y-%m-%d %H:%M:%S %Z')}",
            log_level="info",
        )

        root_path = Path(__file__).parent.parent.parent
        filtered_data_path = root_path / "data" / "processed" / "collab_filtered.csv"
        transformer_path = root_path / "models" / "transformers.joblib"
        save_path = root_path / "data" / "processed" / "transformed_hybrid_data.npz"

        filtered_data = load_filtered_data(filtered_data_path)
        prepared_data = prepare_filtered_data(filtered_data)
        transformed_data = transform_filtered_data(prepared_data, transformer_path)
        save_hybrid_transformed_data(transformed_data, save_path)

    except Exception as e:
        transform_filter_logger.save_logs(
            f"Transform Filtered Data Pipeline failed: {str(e)}",
            log_level="error",
        )
        raise

    else:
        end_time = datetime.now(timezone.utc)
        transform_filter_logger.save_logs(
            f"Transform Filtered Data Pipeline completed at {end_time.strftime('%Y-%m-%d %H:%M:%S %Z')}",
            log_level="info",
        )


if __name__ == "__main__":
    main()
