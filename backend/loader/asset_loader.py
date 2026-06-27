"""
backend/loader/asset_loader.py
=================================
Loads all ML datasets once at startup and attaches them to app.state.
All recommendation routes access data via request.app.state
"""
import numpy as np
import pandas as pd 
from pathlib import Path 
from numpy import load
from scipy.sparse import load_npz
from fastapi import FastAPI
from backend.logging_fastapi.logger_api import prediction_logger
 
# ── Paths ──────────────────────────────────────────────────────────────────────
 
ROOT = Path(__file__).parent.parent.parent  # project root
 
DATA_PATHS = {
    "songs":              ROOT / "data" / "cleaned"   / "songs-info-collab.csv",
    "transformed":        ROOT / "data" / "processed" / "transformed_content_filtering.npz",
    "track_ids":          ROOT / "data" / "processed" / "track_ids.npy",
    "filtered":           ROOT / "data" / "processed" / "collab_filtered.csv",
    "interaction_matrix": ROOT / "data" / "processed" / "interaction_matrix.npz",
    "hybrid_transformed": ROOT / "data" / "processed" / "transformed_hybrid_data.npz",
}
 
 
# ── Loader ─────────────────────────────────────────────────────────────────────
 
async def load_datasets(app: FastAPI) -> None:
    """
    Called once during lifespan startup.
    Attaches all datasets to app.state so every route can access them
    via request.app.state.<name>
    """
    try:
        prediction_logger.save_logs("Loading Pulse Play datasets...")
 
        app.state.songs_data         = pd.read_csv(DATA_PATHS["songs"])
        app.state.transformed_data   = load_npz(DATA_PATHS["transformed"])
        app.state.track_ids          = load(DATA_PATHS["track_ids"], allow_pickle=True)
        app.state.filtered_data      = pd.read_csv(DATA_PATHS["filtered"])
        app.state.interaction_matrix = load_npz(DATA_PATHS["interaction_matrix"])
        app.state.hybrid_transformed = load_npz(DATA_PATHS["hybrid_transformed"])
 
        prediction_logger.save_logs(
            f"Datasets loaded — "
            f"{len(app.state.songs_data)} songs (content), "
            f"{len(app.state.filtered_data)} songs (collab)."
        )
 
    except FileNotFoundError as e:
        prediction_logger.save_logs(f"Dataset file not found: {e}")
        raise  # crash early — app is useless without data
 
    except Exception as e:
        prediction_logger.save_logs(f"Failed to load datasets: {e}")
        raise
 