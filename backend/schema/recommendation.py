"""
backend/schemas/recommendation_schemas.py
==========================================
All Pydantic schemas for the recommendation routes.
"""

from pydantic import BaseModel, Field


# ── Song (used inside RecommendResponse.recommendations list) ─────────────────
class Song(BaseModel):
    """
    Matches your dataset column names exactly:
        df["name"]   → name
        df["artist"] → artist
    These get .title()-cased before returning, so "blinding lights" → "Blinding Lights"
    """
    song_name:                   str
    artist_name:                 str
    pulse_play_preview_url: str | None = None


# ── Base request — shared by all 3 recommenders ───────────────────────────────
class RecommendRequest(BaseModel):
    song_name:   str = Field(..., example="blinding lights")
    artist_name: str = Field(..., example="the weeknd")
    k:           int = Field(5, ge=1, le=20, description="Number of recommendations")


# ── Hybrid extends RecommendRequest — inherits song_name, artist_name, k ──────
class HybridRequest(RecommendRequest):
    """
    Inherits song_name, artist_name, k from RecommendRequest.
    Only adds diversity on top.

    Full body sent from frontend:
    {
        "song_name":   "blinding lights",
        "artist_name": "the weeknd",
        "k":           10,
        "diversity":   5
    }
    """
    diversity: int = Field(5, ge=1, le=10, description="1 = very similar, 10 = more diverse")


# ── Search response ────────────────────────────────────────────────────────────
class SearchResponse(BaseModel):
    """
    Returned by GET /api/song/search.
    Frontend uses found_in_content_db + found_in_collab_db to decide
    which filter options to show:

        found_in_content_db=True,  found_in_collab_db=False
            → show Content-Based only

        found_in_content_db=True,  found_in_collab_db=True
            → show all 3 options, Hybrid selected by default

        found_in_content_db=False, found_in_collab_db=False
            → 404 (handled before this schema is even returned)
    """
    song_name:           str
    artist_name:         str
    found_in_content_db: bool
    found_in_collab_db:  bool


# ── Recommendation response ────────────────────────────────────────────────────
class RecommendResponse(BaseModel):
    song_name:       str
    artist_name:     str
    filter_type:     str
    recommendations: list[Song]



