from fastapi import APIRouter,Request,HTTPException,Depends
from backend.schema.recommendation import Song,RecommendRequest,SearchResponse,HybridRequest,RecommendResponse
from backend.logging_fastapi.logger_api import prediction_logger
from backend.core.dependencies import get_current_user
from backend.core.helpers import _df_to_songs,_song_exists
from Script.recommender_script import collaborative_recommendation,content_recommendation
from Script.hybrid_recommendation import HybridRecommenderSystem
from backend.core.rate_limiter import recommend_rate_limiter

router = APIRouter(prefix="/api")


@router.get(
"/song/search",
response_model=SearchResponse,
summary="Check if a song exists and which filters are available",
tags=["Recommendations"])
async def get_song(
    song_name: str,
    artist_name: str,
    request: Request,
    _ = Depends(get_current_user),
    __ = Depends(recommend_rate_limiter)
):
    ''' 
    GET because we are only checking/reading — no computation triggered yet.
    Frontend calls this silently when user clicks "Get Recommendations".
    Response tells the frontend which filter options to unlock.
    '''
    s,a = song_name.lower() , artist_name.lower()

    in_content = _song_exists(request.app.state.songs_data,   s, a)
    in_collab  = _song_exists(request.app.state.filtered_data, s, a)

    if not in_content and not in_collab:
        prediction_logger.save_logs(f"Song not found: {song_name} by {artist_name}")
        raise HTTPException(
            status_code=404,
            detail=f"'{song_name}' by '{artist_name}' was not found in our database.",
        )
    prediction_logger.save_logs(f"Song found: {song_name} by {artist_name}")

    return SearchResponse(
        song_name=song_name,
        artist_name=artist_name,
        found_in_content_db=in_content,
        found_in_collab_db=in_collab,
    )


@router.post(
"/recommend/content",
response_model=RecommendResponse,
summary="Content-Based recommendations — similar audio features",
tags=["Recommendations"])    
async def get_content_recommendation(
    body: RecommendRequest,
    request: Request,
    _=Depends(get_current_user),
    __=Depends(recommend_rate_limiter)
):
    '''
    POST because we are triggering ML inference, not just reading data.
    Frontend chains this automatically after a successful /song/search.
    '''

    s, a = body.song_name.lower(), body.artist_name.lower()

    if not _song_exists(request.app.state.songs_data, s, a):
        raise HTTPException(
            status_code=404,
            detail=f"'{body.song_name}' not found in content database.",
        )
    
    prediction_logger.save_logs(f"Content recommendation: {body.song_name} by {body.artist_name}")
 
    results = content_recommendation(
        song_name=s,
        artist_name=a,
        songs_data=request.app.state.songs_data,
        transformed_data=request.app.state.transformed_data,
        k=body.k,
    )
 
    return RecommendResponse(
        song_name=body.song_name,
        artist_name=body.artist_name,
        filter_type="Content-Based Filtering",
        recommendations=_df_to_songs(results),
    )
    

# ── 3. Collaborative ──────────────────────────────────────────────────────────

@router.post(
"/recommend/collaborative",
response_model=RecommendResponse,
summary="Collaborative recommendations — based on User History patterns",
tags=["Recommendations"])
async def get_collab_recommendation(
    body: RecommendRequest,
    request: Request,
    _ = Depends(get_current_user),
    __ = Depends(recommend_rate_limiter)
):
    '''
    POST — same reasoning, ML computation triggered.
    Only available if found_in_collab_db was True in the search response.
    '''
    s, a = body.song_name.lower(), body.artist_name.lower()
 
    if not _song_exists(request.app.state.filtered_data, s, a):
        raise HTTPException(
            status_code=404,
            detail=f"'{body.song_name}' not found in collaborative database.",
        )
 
    prediction_logger.save_logs(f"Collaborative recommendation: {body.song_name} by {body.artist_name}")
 
    results = collaborative_recommendation(
        song_name=s,
        artist_name=a,
        track_ids=request.app.state.track_ids,
        songs_data=request.app.state.filtered_data,
        interaction_matrix=request.app.state.interaction_matrix,
        k=body.k,
    )
 
    return RecommendResponse(
        song_name=body.song_name,
        artist_name=body.artist_name,
        filter_type="Collaborative Filtering",
        recommendations=_df_to_songs(results),
    )


# ── 4. Hybrid ─────────────────────────────────────────────────────────────────

@router.post(
    "/recommend/hybrid",
    response_model=RecommendResponse,
    summary="Hybrid recommendations — blend of content + collaborative",
    tags=["Recommendations"],
)
async def get_hybrid_recommendation(
    body: HybridRequest,
    request: Request,
    _ = Depends(get_current_user),
    __ = Depends(recommend_rate_limiter)
):
    s, a = body.song_name.lower(), body.artist_name.lower()

    if not _song_exists(request.app.state.filtered_data, s, a):
        raise HTTPException(
            status_code=404,
            detail=f"'{body.song_name}' not found in hybrid database.",
        )
    
    content_weight = 1 - (body.diversity / 10)  # same formula as your Streamlit app
 
    prediction_logger.save_logs(
        f"Hybrid recommendation: {body.song_name} by {body.artist_name} "
        f"| diversity={body.diversity} | content_weight={content_weight}"
    )
 
    recommender = HybridRecommenderSystem(
        num_of_recommendations=body.k,
        weight_content_based=content_weight,
    )

    results = recommender.give_recommendation(
        song_name=s,
        artist_name=a,
        songs_data=request.app.state.filtered_data,
        transformed_matrix=request.app.state.hybrid_transformed,
        track_ids=request.app.state.track_ids,
        interaction_matrix=request.app.state.interaction_matrix,
    )
 
    return RecommendResponse(
        song_name=body.song_name,
        artist_name=body.artist_name,
        filter_type="Hybrid Recommender System",
        recommendations=_df_to_songs(results),
    )
