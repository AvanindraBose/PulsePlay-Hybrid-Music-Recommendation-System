import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity


class HybridRecommenderSystem:
    """
    Generates recommendations from weighted content and collaborative similarities.
    """

    def __init__(self, num_of_recommendations: int, weight_content_based: float):
        """
        Initializes the hybrid recommender.

        Parameters:
        num_of_recommendations (int): Number of recommendations to return.
        weight_content_based (float): Weight assigned to content-based scores.
        """
        if num_of_recommendations <= 0:
            raise ValueError("num_of_recommendations must be greater than 0")

        if not 0 <= weight_content_based <= 1:
            raise ValueError("weight_content_based must be between 0 and 1")

        self.num_recomm = num_of_recommendations
        self.weight_content_based = weight_content_based
        self.weight_collab_based = 1 - self.weight_content_based

    def _get_seed_song(
        self,
        song_name: str,
        artist_name: str,
        songs_data: pd.DataFrame,
    ) -> pd.Series:
        """
        Finds the seed song row in the songs metadata.

        Parameters:
        song_name (str): Name of the seed song.
        artist_name (str): Artist name for the seed song.
        songs_data (pd.DataFrame): Song metadata.

        Returns:
        pd.Series: Matching seed song row.
        """
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
            raise ValueError(f"Song not found: '{song_name}' by '{artist_name}'")

        return song_row.iloc[0]

    def _calculate_content_based_similarities(
        self,
        song_index: int,
        transformed_matrix,
    ) -> np.ndarray:
        """
        Calculates content-based similarity scores for the seed song.

        Parameters:
        song_index (int): Row index of the seed song in the transformed matrix.
        transformed_matrix: Content feature matrix aligned with songs_data rows.

        Returns:
        np.ndarray: Content similarity scores.
        """
        input_vector = transformed_matrix[song_index]
        return cosine_similarity(input_vector, transformed_matrix).ravel()

    def _calculate_collab_based_similarities(
        self,
        input_track_id: str,
        track_ids: np.ndarray,
        interaction_matrix,
    ) -> np.ndarray:
        """
        Calculates collaborative similarity scores for the seed song.

        Parameters:
        input_track_id (str): Track ID for the seed song.
        track_ids (np.ndarray): Track IDs aligned with interaction matrix rows.
        interaction_matrix: Track-user interaction matrix.

        Returns:
        np.ndarray: Collaborative similarity scores.
        """
        matching_indices = np.where(track_ids == input_track_id)[0]
        if len(matching_indices) == 0:
            raise ValueError(f"Track ID not found in interaction matrix: {input_track_id}")

        song_index = matching_indices[0]
        input_vector = interaction_matrix[song_index]
        return cosine_similarity(input_vector, interaction_matrix).ravel()

    def _normalize_similarities(self, similarity_scores: np.ndarray) -> np.ndarray:
        """
        Normalizes similarity scores to the range 0 to 1.

        Parameters:
        similarity_scores (np.ndarray): Similarity scores to normalize.

        Returns:
        np.ndarray: Normalized similarity scores.
        """
        minimum = np.min(similarity_scores)
        maximum = np.max(similarity_scores)

        if maximum == minimum:
            return np.zeros_like(similarity_scores, dtype=float)

        return (similarity_scores - minimum) / (maximum - minimum)

    def _weighted_scores(
        self,
        content_based_scores: np.ndarray,
        collab_based_scores: np.ndarray,
    ) -> np.ndarray:
        """
        Combines content and collaborative scores using configured weights.

        Parameters:
        content_based_scores (np.ndarray): Normalized content scores.
        collab_based_scores (np.ndarray): Normalized collaborative scores.

        Returns:
        np.ndarray: Weighted hybrid scores.
        """
        return (
            self.weight_content_based * content_based_scores
            + self.weight_collab_based * collab_based_scores
        )

    def give_recommendation(
        self,
        song_name: str,
        artist_name: str,
        songs_data: pd.DataFrame,
        transformed_matrix,
        track_ids: np.ndarray,
        interaction_matrix,
    ) -> pd.DataFrame:
        """
        Generates top hybrid recommendations for a seed song.

        Parameters:
        song_name (str): Name of the seed song.
        artist_name (str): Artist name for the seed song.
        songs_data (pd.DataFrame): Collaborative-filtered song metadata.
        transformed_matrix: Content feature matrix aligned with songs_data rows.
        track_ids (np.ndarray): Track IDs aligned with interaction matrix rows.
        interaction_matrix: Track-user interaction matrix.

        Returns:
        pd.DataFrame: Top hybrid song recommendations.
        """
        seed_song = self._get_seed_song(song_name, artist_name, songs_data)
        input_track_id = seed_song["track_id"]
        song_index = seed_song.name

        content_based_similarities = self._calculate_content_based_similarities(
            song_index=song_index,
            transformed_matrix=transformed_matrix,
        )
        collab_based_similarities = self._calculate_collab_based_similarities(
            input_track_id=input_track_id,
            track_ids=track_ids,
            interaction_matrix=interaction_matrix,
        )

         # normalize content based similarities
        normalized_content_based_similarities = self._normalize_similarities(content_based_similarities)
        
        # normalize collaborative filtering similarities
        normalized_collaborative_filtering_similarities = self._normalize_similarities(collab_based_similarities)
        
        # weighted combination of similarities
        weighted_scores = self._weighted_scores(content_based_scores= normalized_content_based_similarities, 
                                                    collab_based_scores= normalized_collaborative_filtering_similarities)
        
        
        # index values of recommendations
        recommendation_indices = np.argsort(weighted_scores.ravel())[-self.num_recomm -1:][::-1] 
        
        # get top k recommendations
        recommendation_track_ids = track_ids[recommendation_indices]
       
        # get top scores
        top_scores = np.sort(weighted_scores.ravel())[-self.num_recomm -1:][::-1]
        
        # get the songs from data and print
        scores_df = pd.DataFrame({"track_id":recommendation_track_ids.tolist(),
                                "score":top_scores})
        top_k_songs = (
                        songs_data
                        .loc[songs_data["track_id"].isin(recommendation_track_ids)]
                        .merge(scores_df,on="track_id")
                        .sort_values(by="score",ascending=False)
                        .drop(columns=["track_id","score"])
                        .reset_index(drop=True)
                        )
        
        return top_k_songs
