import time
from fastapi import APIRouter,Request,HTTPException,Depends,status
from backend.schema.recommendation import Song,RecommendRequest,SearchResponse,HybridRequest,RecommendResponse
from backend.logging_fastapi.logger_api import prediction_logger
from backend.core.dependencies import get_current_user
from backend.core.helpers import _df_to_songs,_song_exists
from Script.recommender_script import collaborative_recommendation,content_recommendation
from Script.hybrid_recommendation import HybridRecommenderSystem
from backend.core.rate_limiter import recommend_rate_limiter
from backend.custom_metrics import (
    REQUEST_COUNT,
    REQUEST_DURATION,
    REQUEST_ERRORS,
    RESPONSE_STATUS,
    RECOMMENDATION_COUNTER,
    RECOMMENDATION_INFERENCE_DURATION,
    RECOMMENDATION_RESULT_COUNT,
    SEARCH_RESULTS,
    SONG_NAME_LENGTH,
    ARTIST_NAME_LENGTH 
)

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
    try: 
        start_time = time.perf_counter()
        status_code = "200"
        endpoint = request.url.path
        method = request.method
        REQUEST_COUNT.labels(method=method,endpoint=endpoint).inc()
        SONG_NAME_LENGTH.observe(len(song_name))
        ARTIST_NAME_LENGTH.observe(len(artist_name))

        s,a = song_name.lower() , artist_name.lower()

        in_content = _song_exists(request.app.state.songs_data,   s, a)
        in_collab  = _song_exists(request.app.state.filtered_data, s, a)

        if not in_content and not in_collab:

            prediction_logger.save_logs(f"Song not found: {song_name} by {artist_name}")
            REQUEST_ERRORS.labels(method=method, endpoint=endpoint, error_type="missing_song").inc()
            SEARCH_RESULTS.labels(status="not found").inc()

            raise HTTPException(
                status_code=404,
                detail=f"Apologies!!, Currently '{song_name}' by '{artist_name}' is not in our Application. We will add it soon",
            )
        
        SEARCH_RESULTS.labels(status="found").inc()
        
    except HTTPException as exc:
        status_code = str(exc.status_code)

        REQUEST_ERRORS.labels(
            method=method,
            endpoint=endpoint,
            error_type=exc.__class__.__name__,
        ).inc()

        prediction_logger.save_logs(f"HTTP Exception: {exc.detail}",log_level="warning")
        raise


    except Exception as exc:

        status_code = "500"

        REQUEST_ERRORS.labels(
            method=method,
            endpoint=endpoint,
            error_type=exc.__class__.__name__).inc()

        prediction_logger.save_logs(f"Unexpected recommendation error: {exc}",log_level="error",)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Error"
        )
    
    else:
        prediction_logger.save_logs(f"Song found: {song_name} by {artist_name}")
        return SearchResponse(
            song_name=song_name,
            artist_name=artist_name,
            found_in_content_db=in_content,
            found_in_collab_db=in_collab,
        )
    
    finally:
        REQUEST_DURATION.labels(method=method,endpoint=endpoint).observe(time.perf_counter() - start_time)
        RESPONSE_STATUS.labels(method=method,endpoint=endpoint,status_code=status_code).inc()



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
    try: 
        start_time = time.perf_counter()
        endpoint = request.url.path
        method = request.method
        status_code = "200"
        REQUEST_COUNT.labels(method=method,endpoint=endpoint).inc()
        SONG_NAME_LENGTH.observe(len(body.song_name))
        ARTIST_NAME_LENGTH.observe(len(body.artist_name))

        s, a = body.song_name.lower(), body.artist_name.lower()

        if not _song_exists(request.app.state.songs_data, s, a):

            SEARCH_RESULTS.labels(status="not found").inc()

            raise HTTPException(
                status_code=404,
                detail=f"'{body.song_name}' not found in content database.",
            )
        SEARCH_RESULTS.labels(status="found").inc()
        prediction_logger.save_logs(f"Generating Content recommendation for: {body.song_name} by {body.artist_name}")

        inference_start = time.perf_counter()
        results = content_recommendation(
            song_name=s,
            artist_name=a,
            songs_data=request.app.state.songs_data,
            transformed_data=request.app.state.transformed_data,
            k=body.k,
        )

        RECOMMENDATION_INFERENCE_DURATION.observe(time.perf_counter() - inference_start)

    except HTTPException as exc:
        status_code = str(exc.status_code)

        REQUEST_ERRORS.labels(
            method=method,
            endpoint=endpoint,
            error_type=exc.__class__.__name__,
        ).inc()

        prediction_logger.save_logs(f"HTTP Exception: {exc.detail}",log_level="warning")
        raise


    except Exception as exc:

        status_code = "500"

        REQUEST_ERRORS.labels(
            method=method,
            endpoint=endpoint,
            error_type=exc.__class__.__name__).inc()

        prediction_logger.save_logs(f"Unexpected recommendation error: {exc}",log_level="error",)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Error"
        )
    
    else:

        prediction_logger.save_logs(f"Content recommendation successfully recieved for : {body.song_name} by {body.artist_name}")
        RECOMMENDATION_COUNTER.labels(recommendation_type="content").inc()
        RECOMMENDATION_RESULT_COUNT.observe(len(results))

        return RecommendResponse(
            song_name=body.song_name,
            artist_name=body.artist_name,
            filter_type="Content-Based Filtering",
            recommendations=_df_to_songs(results),
        )
    
    finally:
        REQUEST_DURATION.labels(method=method,endpoint=endpoint).observe(time.perf_counter() - start_time)
        RESPONSE_STATUS.labels(method=method,endpoint=endpoint,status_code=status_code).inc()
    
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
    try:
        start_time = time.perf_counter()
        endpoint = request.url.path
        method = request.method
        status_code = "200"
        REQUEST_COUNT.labels(method=method,endpoint=endpoint).inc()
        SONG_NAME_LENGTH.observe(len(body.song_name))
        ARTIST_NAME_LENGTH.observe(len(body.artist_name))

        s, a = body.song_name.lower(), body.artist_name.lower()
    
        if not _song_exists(request.app.state.filtered_data, s, a):
            SEARCH_RESULTS.labels(status="not found").inc()
            raise HTTPException(
                status_code=404,
                detail=f"'{body.song_name}' not found in collaborative database.",
            )
        
        SEARCH_RESULTS.labels(status="found").inc()
    
        prediction_logger.save_logs(f"Generating Collaborative recommendation for : {body.song_name} by {body.artist_name}")

        inference_start = time.perf_counter()

        results = collaborative_recommendation(
            song_name=s,
            artist_name=a,
            track_ids=request.app.state.track_ids,
            songs_data=request.app.state.filtered_data,
            interaction_matrix=request.app.state.interaction_matrix,
            k=body.k,
        )

        RECOMMENDATION_INFERENCE_DURATION.observe(time.perf_counter() - inference_start)
    
    except HTTPException as exc:
        status_code = str(exc.status_code)

        REQUEST_ERRORS.labels(
            method=method,
            endpoint=endpoint,
            error_type=exc.__class__.__name__,
        ).inc()

        prediction_logger.save_logs(f"HTTP Exception: {exc.detail}",log_level="warning")
        raise


    except Exception as exc:

        status_code = "500"

        REQUEST_ERRORS.labels(
            method=method,
            endpoint=endpoint,
            error_type=exc.__class__.__name__).inc()

        prediction_logger.save_logs(f"Unexpected recommendation error: {exc}",log_level="error",)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Error"
        )
    
    else :
        prediction_logger.save_logs("Collaborative Recommendation Successfully Completed.",log_level='info')
        RECOMMENDATION_COUNTER.labels(recommendation_type="collaborative").inc()
        RECOMMENDATION_RESULT_COUNT.observe(len(results))

        return RecommendResponse(
            song_name=body.song_name,
            artist_name=body.artist_name,
            filter_type="Collaborative Filtering",
            recommendations=_df_to_songs(results),
        )
    finally:
        REQUEST_DURATION.labels(method=method,endpoint=endpoint).observe(time.perf_counter() - start_time)
        RESPONSE_STATUS.labels(method=method,endpoint=endpoint,status_code=status_code).inc()




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
    try:
        start_time = time.perf_counter()
        endpoint = request.url.path
        method = request.method
        status_code = "200"
        REQUEST_COUNT.labels(method=method,endpoint=endpoint).inc()
        SONG_NAME_LENGTH.observe(len(body.song_name))
        ARTIST_NAME_LENGTH.observe(len(body.artist_name))

        s, a = body.song_name.lower(), body.artist_name.lower()

        if not _song_exists(request.app.state.filtered_data, s, a):
            SEARCH_RESULTS.labels(status="not found").inc()

            raise HTTPException(
                status_code=404,
                detail=f"'{body.song_name}' not found in hybrid database.",
            )
        
        SEARCH_RESULTS.labels(status="found").inc()

        content_weight = 1 - (body.diversity / 10)
    
        prediction_logger.save_logs(
            f"Generating Hybrid recommendation for : {body.song_name} by {body.artist_name} "
            f"| diversity={body.diversity} | content_weight={content_weight}"
        )

        recommender = HybridRecommenderSystem(
            num_of_recommendations=body.k,
            weight_content_based=content_weight,
        )

        inference_start = time.perf_counter()

        results = recommender.give_recommendation(
            song_name=s,
            artist_name=a,
            songs_data=request.app.state.filtered_data,
            transformed_matrix=request.app.state.hybrid_transformed,
            track_ids=request.app.state.track_ids,
            interaction_matrix=request.app.state.interaction_matrix,
        )

        RECOMMENDATION_INFERENCE_DURATION.observe(time.perf_counter() - inference_start)
    
    except HTTPException as exc:
        status_code = str(exc.status_code)

        REQUEST_ERRORS.labels(
            method=method,
            endpoint=endpoint,
            error_type=exc.__class__.__name__,
        ).inc()

        prediction_logger.save_logs(f"HTTP Exception: {exc.detail}",log_level="warning")
        raise


    except Exception as exc:

        status_code = "500"

        REQUEST_ERRORS.labels(
            method=method,
            endpoint=endpoint,
            error_type=exc.__class__.__name__).inc()

        prediction_logger.save_logs(f"Unexpected recommendation error: {exc}",log_level="error",)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Error"
        )
    
    else: 
        prediction_logger.save_logs(
            f"Successfull Hybrid recommendation for : {body.song_name} by {body.artist_name} "
            f"| diversity={body.diversity} | content_weight={content_weight}"
        )
        RECOMMENDATION_COUNTER.labels(recommendation_type="hybrid").inc()
        RECOMMENDATION_RESULT_COUNT.observe(len(results))

        return RecommendResponse(
            song_name=body.song_name,
            artist_name=body.artist_name,
            filter_type="Hybrid Recommender System",
            recommendations=_df_to_songs(results),
        )
