from prometheus_client import Counter, Histogram

# ==========================================================
# API Metrics
# ==========================================================

REQUEST_COUNT = Counter(
    name="http_requests_total",
    documentation="Total number of HTTP requests handled by the API",
    labelnames=["method", "endpoint"],
)

REQUEST_DURATION = Histogram(
    name="http_request_duration_seconds",
    documentation="Duration of HTTP requests in seconds",
    labelnames=["method", "endpoint"],
)

REQUEST_ERRORS = Counter(
    name="http_request_errors_total",
    documentation="Count of failed HTTP requests by endpoint and error type",
    labelnames=["method", "endpoint", "error_type"],
)

# Keeping this either 200 or 500 and reducing the cardinality.
# Main purpose of this metric is to tell how much our application is giving 200 responses vs 500
RESPONSE_STATUS = Counter(
    name="http_response_status_total",
    documentation="HTTP response status codes emitted by the API",
    labelnames=["method", "endpoint", "status_code"],
)

# ==========================================================
# Recommendation Metrics
# ==========================================================

RECOMMENDATION_COUNTER = Counter(
    name="recommendations_total",
    documentation="Total recommendation requests served by each recommendation engine",
    labelnames=["recommendation_type"],  # content | collaborative | hybrid
)

RECOMMENDATION_INFERENCE_DURATION = Histogram(
    name="recommendation_inference_duration_seconds",
    documentation="Time spent generating recommendations",
)

RECOMMENDATION_RESULT_COUNT = Histogram(
    name="recommendation_result_count",
    documentation="Distribution of the number of recommendations returned",
    buckets=[5,10,15, 20],
)

# ==========================================================
# Input Metrics
# ==========================================================

SONG_NAME_LENGTH = Histogram(
    name="song_name_length_characters",
    documentation="Distribution of song name lengths",
    buckets=[10, 25, 50, 100, 200],
)

ARTIST_NAME_LENGTH = Histogram(
    name="artist_name_length_characters",
    documentation="Distribution of artist name lengths",
    buckets=[10, 25, 50, 100, 200],
)

# ==========================================================
# Search Metrics
# ==========================================================

SEARCH_RESULTS = Counter(
    name="search_requests_total",
    documentation="Song search results",
    labelnames=["status"],  # found | not_found
)

# ==========================================================
# Cache Metrics
# ==========================================================

CACHE_HITS = Counter(
    name="cache_hits_total",
    documentation="Total number of cache hits",
    labelnames=["endpoint"],
)

CACHE_MISSES = Counter(
    name="cache_misses_total",
    documentation="Total number of cache misses",
    labelnames=["endpoint"],
)

CACHE_WRITES = Counter(
    name="cache_writes_total",
    documentation="Total number of cache writes",
    labelnames=["endpoint"],
)