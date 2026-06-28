FROM python:3.11-slim AS builder

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.11-slim AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copying the entire data folder
COPY ./data/cleaned/songs-info-collab.csv data/cleaned/songs-info-collab.csv
COPY ./data/processed/transformed_content_filtering.npz data/processed/transformed_content_filtering.npz
COPY ./data/processed/track_ids.npy data/processed/track_ids.npy
COPY ./data/processed/collab_filtered.csv data/processed/collab_filtered.csv
COPY ./data/processed/interaction_matrix.npz data/processed/interaction_matrix.npz
COPY ./data/processed/transformed_hybrid_data.npz data/processed/transformed_hybrid_data.npz

# Copying Entire Backend Service Logic
COPY --from=builder /app/.venv ./.venv
COPY ./backend/ backend/
COPY ./Script/hybrid_recommendation.py Script/hybrid_recommendation.py
COPY ./Script/recommender_script.py Script/recommender_script.py
COPY ./src/utils/ src/utils/

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]