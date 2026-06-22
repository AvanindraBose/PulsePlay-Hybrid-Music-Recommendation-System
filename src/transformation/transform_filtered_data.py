import pandas as pd
from pathlib import Path
from src.data.data_cleaning import data_for_content_filtering
from src.content_based_filtering.content_filtering import transform_data, save_transformed_data


def main()-> None:
    # load the filtered data
    root_path = Path(__file__).parent.parent.parent

    filtered_data_path = root_path / "data" / "processed" / "collab_filtered.csv"

    transformer_path = root_path / "models"
    transformer_name = "transformers.joblib"

    save_path = root_path / "data" / "processed" / "transformed_hybrid_data.npz"

    filtered_data = pd.read_csv(filtered_data_path)

    # clean the data
    filtered_data_cleaned = data_for_content_filtering(filtered_data)

    # transform the data into matrix
    transformed_data = transform_data(filtered_data_cleaned , transformer_path/transformer_name)

    # save the transformed data
    save_transformed_data(transformed_data, save_path)
    

if __name__ == "__main__":
    main()