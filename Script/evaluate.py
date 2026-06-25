import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.model_selection import train_test_split
 
 
# ─────────────────────────────────────────────
# STEP 1 — Generate synthetic dataset
# ─────────────────────────────────────────────
 
def generate_dataset() -> pd.DataFrame:
    """
    Creates a synthetic dataset with 6 users and 5 tracks.
    Playcount > 0 means the user listened to that track.
    Replace this with pd.read_csv() for your real dataset.
    """
    data = {
        "user_id":   ["u1","u1","u1","u1","u2","u2","u2","u3","u3","u3",
                       "u4","u4","u5","u5","u5","u6","u6","u6"],
        "track_id":  ["t1","t2","t3","t4","t1","t3","t5","t2","t4","t5",
                       "t1","t2","t3","t4","t5","t1","t3","t4"],
        "playcount": [  5,   3,   4,   4,   2,   5,   1,   4,   3,   2,
                        1,   5,   3,   4,   4,   2,   3,   5 ],
    }
    return pd.DataFrame(data)
 
 
# ─────────────────────────────────────────────
# STEP 2 — Per-user 80/20 random hold-out split
# ─────────────────────────────────────────────
 
def split_train_test( 
    df: pd.DataFrame,
    test_size: float = 0.2,
    min_interactions: int = 2,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    For each user, randomly holds out 20% of their interactions as test.
    Only keeps users with enough interactions to split meaningfully.
 
    Train → model learns from this (builds the user-item matrix)
    Test  → ground truth (did the model recommend these tracks?)
 
    No data leakage: test tracks are completely hidden from the model.
    """
    train_rows = []
    test_rows  = []
 
    for user_id, group in df.groupby("user_id"):
        # only keep tracks the user actually listened to
        listened = group[group["playcount"] > 0]
 
        if len(listened) < min_interactions:
            # not enough history to split — put everything in train
            train_rows.append(listened)
            continue
 
        train, test = train_test_split(
            listened,
            test_size=test_size,
            random_state=random_state,
        )
        train_rows.append(train)
        test_rows.append(test)
 
    train_df = pd.concat(train_rows).reset_index(drop=True)
    test_df  = pd.concat(test_rows).reset_index(drop=True)
 
    return train_df, test_df
 
 
# ─────────────────────────────────────────────
# STEP 3 — Build user-item matrix from TRAIN only
# ─────────────────────────────────────────────
 
def build_user_item_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """
    Pivot train interactions into a user x item matrix.
    The model only sees training data — test tracks are invisible here.
    """
    matrix = df.pivot_table(
        index="user_id",
        columns="track_id",
        values="playcount",
        aggfunc="sum",
        fill_value=0,
    )
    return matrix
 
 
# ─────────────────────────────────────────────
# STEP 4 — Compute item-item similarity
# ─────────────────────────────────────────────
 
def compute_item_similarity(user_item_matrix: pd.DataFrame) -> pd.DataFrame:
    """
    Cosine similarity between every pair of items.
    Computed on TRAIN matrix only.
    """
    item_matrix = user_item_matrix.T      # shape: items x users
    sim_values  = cosine_similarity(item_matrix)
    similarity  = pd.DataFrame(
        sim_values,
        index=item_matrix.index,
        columns=item_matrix.index,
    )
    return similarity
 
 
# ─────────────────────────────────────────────
# STEP 5 — Generate top-K recommendations
# ─────────────────────────────────────────────
 
def recommend_for_user(
    user_id: str,
    user_item_matrix: pd.DataFrame,
    item_similarity: pd.DataFrame,
    k: int = 3,
) -> list[str]:
    """
    Recommends tracks the user has NOT played in train set.
    Scores each candidate by summing its similarity to all
    tracks the user has played, weighted by playcount.
    """
    played_tracks   = user_item_matrix.loc[user_id]
    played_tracks   = played_tracks[played_tracks > 0].index.tolist()
    all_tracks      = user_item_matrix.columns.tolist()
    unplayed_tracks = [t for t in all_tracks if t not in played_tracks]
 
    if not played_tracks or not unplayed_tracks:
        return []
 
    scores = {}
    for candidate in unplayed_tracks:
        score = sum(
            item_similarity.loc[candidate, played]
            * user_item_matrix.loc[user_id, played]
            for played in played_tracks
            if candidate in item_similarity.index
            and played   in item_similarity.columns
        )
        scores[candidate] = score
 
    ranked = sorted(scores, key=scores.get, reverse=True)
    return ranked[:k]
 
 
def recommend_all_users(
    user_item_matrix: pd.DataFrame,
    item_similarity: pd.DataFrame,
    k: int = 3,
) -> dict[str, list[str]]:
    recommendations = {}
    for user_id in user_item_matrix.index:
        recommendations[user_id] = recommend_for_user(
            user_id, user_item_matrix, item_similarity, k
        )
    return recommendations
 
 
# ─────────────────────────────────────────────
# STEP 6 — Build ground truth from TEST set
# ─────────────────────────────────────────────
 
def build_ground_truth(test_df: pd.DataFrame) -> dict[str, set[str]]:
    """
    Ground truth = tracks each user interacted with in the TEST set.
    These are the tracks we hid from the model.
    The model should ideally recommend these.
    """
    ground_truth = {}
    for user_id, group in test_df.groupby("user_id"):
        ground_truth[user_id] = set(group["track_id"].tolist())
    return ground_truth
 
 
# ─────────────────────────────────────────────
# STEP 7 — Precision@K and Recall@K
# ─────────────────────────────────────────────
 
def precision_at_k(recommended: list[str], relevant: set[str], k: int) -> float:
    """
    Of the K things we recommended, how many were actually in the test set?
    """
    if k == 0:
        return 0.0
    hits = len([t for t in recommended[:k] if t in relevant])
    return hits / k
 
 
def recall_at_k(recommended: list[str], relevant: set[str], k: int) -> float:
    """
    Of all the test tracks, how many did we surface in top-K?
    """
    if not relevant:
        return 0.0
    hits = len([t for t in recommended[:k] if t in relevant])
    return hits / len(relevant)
 
 
def evaluate(
    recommendations: dict[str, list[str]],
    ground_truth: dict[str, set[str]],
    k: int,
) -> pd.DataFrame:
    """
    Computes Precision@K and Recall@K per user and prints macro averages.
    Only evaluates users who appear in both recommendations and ground truth.
    """
    rows = []
 
    # only evaluate users who have test ground truth
    for user_id, relevant in ground_truth.items():
        recommended = recommendations.get(user_id, [])
        p = precision_at_k(recommended, relevant, k)
        r = recall_at_k(recommended, relevant, k)
        rows.append({
            "user_id":        user_id,
            "recommended":    recommended,
            "relevant":       sorted(relevant),
            f"precision@{k}": round(p, 4),
            f"recall@{k}":    round(r, 4),
        })
 
    results_df    = pd.DataFrame(rows)
    avg_precision = results_df[f"precision@{k}"].mean()
    avg_recall    = results_df[f"recall@{k}"].mean()
 
    print(f"\n{'='*60}")
    print(f"  Evaluation Results  (K = {k})")
    print(f"{'='*60}")
    print(results_df[["user_id", "recommended", "relevant",
                       f"precision@{k}", f"recall@{k}"]].to_string(index=False))
    print(f"\n  Mean Precision@{k} : {avg_precision:.4f}")
    print(f"  Mean Recall@{k}    : {avg_recall:.4f}")
    print(f"{'='*60}\n")
 
    return results_df
 
 
# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
 
def main():
    K = 3
 
    # Step 1 — load data
    df = generate_dataset()
    print("Raw interaction data:")
    print(df.to_string(index=False))
 
    # Step 2 — split per user (NO data leakage)
    train_df, test_df = split_train_test(df, test_size=0.2)
    print(f"\nTrain interactions : {len(train_df)}")
    print(f"Test  interactions : {len(test_df)}")
    print("\nTest set (ground truth — hidden from model):")
    print(test_df.to_string(index=False))
 
    # Step 3 — build matrix from TRAIN only
    user_item_matrix = build_user_item_matrix(train_df)
    print("\nUser-Item Matrix (train only):")
    print(user_item_matrix)
 
    # Step 4 — similarity on TRAIN only
    item_similarity = compute_item_similarity(user_item_matrix)
    print("\nItem-Item Cosine Similarity:")
    print(item_similarity.round(4))
 
    # Step 5 — recommend
    recommendations = recommend_all_users(user_item_matrix, item_similarity, k=K)
    print(f"\nTop-{K} Recommendations per user:")
    for user, recs in recommendations.items():
        print(f"  {user}: {recs}")
 
    # Step 6 — ground truth from TEST set
    ground_truth = build_ground_truth(test_df)
    print(f"\nGround Truth (from test set — hidden from model):")
    for user, relevant in ground_truth.items():
        print(f"  {user}: {sorted(relevant)}")
 
    # Step 7 — evaluate
    results = evaluate(recommendations, ground_truth, k=K)
 
    return results
 
 
if __name__ == "__main__":
    main()