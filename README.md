Pulse Play Hybrid Music Recommendation System
==============================

Creating a Hybrid Music Recommendation System.

Architecture Diagrams
------------

The project has two architecture views: the offline ML training pipeline and the online ML inference pipeline. The exported architecture diagrams are available in [`docs/diagrams`](docs/diagrams):

- [`Pulse-Play-Hybrid-RecSys-ML Training Pipeline.drawio.png`](docs/diagrams/Pulse-Play-Hybrid-RecSys-ML%20Training%20Pipeline.drawio.png)
- [`Pulse-Play-Hybrid-RecSys-ML Inference Pipeline.drawio.png`](docs/diagrams/Pulse-Play-Hybrid-RecSys-ML%20Inference%20Pipeline.drawio.png)

Editable diagrams.net sources are available at [`docs/pulse-play-architecture.drawio`](docs/pulse-play-architecture.drawio) and [`docs/Pulse-Play-Hybrid-RecSys-MLTrainingPipeline.drawio`](docs/Pulse-Play-Hybrid-RecSys-MLTrainingPipeline.drawio).

### ML Training Pipeline

![ML Training Pipeline](docs/diagrams/Pulse-Play-Hybrid-RecSys-ML%20Training%20Pipeline.drawio.png)

This pipeline is intentionally not a simple straight-line training flow. The content-based and collaborative-filtering branches create different artifacts, and the hybrid stage depends on both of them.

- **Amazon S3 + DVC Remote**: Stores versioned raw datasets and pipeline artifacts outside the Git repository. The repo keeps `.dvc` pointers while the large files live in remote storage.
- **DVC Pipeline Orchestration**: Defines and reproduces the dependency graph in `dvc.yaml`. It decides which stages need to run when data or code changes.
- **Raw Data**: Starts from `songs-info.csv` and `user-info.csv`. Song metadata powers content features, while user listening history powers collaborative filtering.
- **Data Cleaning**: Deduplicates songs, normalizes text fields, handles missing tags, and creates two downstream catalogs: one for content filtering and one for collaborative filtering.
- **Content Feature Pipeline**: Builds the reusable feature transformer using text tags, categorical features, and audio features. It produces the content feature matrix and the fitted transformer artifact.
- **Collaborative Pipeline**: Uses user listening history to find tracks with behavioral data, builds the track-user interaction matrix, and creates the filtered collaborative catalog.
- **Hybrid Feature Alignment**: This is the key dependency. The hybrid matrix is created only after collaborative filtering produces the filtered catalog, then the content transformer is reused on that filtered catalog.
- **Versioned ML Artifacts**: The final serving artifacts include sparse matrices, the fitted transformer, filtered catalog, interaction matrix, and track indexes.
- **AWS ECR Image**: The inference container packages the FastAPI service with the generated artifacts so the serving layer can load them at startup.

Interview talking point: the system separates expensive offline artifact generation from fast online inference. The hybrid recommender is not an independent model; it is an artifact alignment step that combines collaborative eligibility with content-based feature representation.

### ML Inference Pipeline

![ML Inference Pipeline](docs/diagrams/Pulse-Play-Hybrid-RecSys-ML%20Inference%20Pipeline.drawio.png)

The inference pipeline serves authenticated recommendation requests and uses precomputed ML artifacts instead of retraining anything at request time.

- **User Browser Dashboard**: The frontend lets users search for a song, choose content/collaborative/hybrid recommendation mode, set recommendation count, and adjust hybrid diversity.
- **AWS ALB / API Gateway**: Represents the production entry point for routing HTTPS traffic to the API service.
- **FastAPI Recommender API**: Serves auth pages, dashboard pages, health checks, metrics, and recommendation endpoints. It loads all ML artifacts during application startup.
- **Auth Layer**: Uses JWT access cookies and refresh-token flow to protect the dashboard and recommendation APIs.
- **Amazon RDS PostgreSQL**: Stores users and refresh tokens through async SQLAlchemy models.
- **ElastiCache Redis**: Supports two production-critical paths: recommendation response caching and request rate-limiting counters.
- **In-memory ML Artifacts**: The API loads content, collaborative, and hybrid matrices once into `app.state`, along with the filtered catalog and track indexes.
- **Recommendation Engine**: Handles search availability, content similarity, collaborative similarity, and hybrid weighted scoring.
- **Ranked Recommendations**: Returns song name, artist, and preview URL data to the dashboard.
- **Observability**: Prometheus metrics track request count, latency, errors, cache hits/misses, inference duration, and result counts. Redis exporter and logs make the service easier to monitor.
- **Health Checks**: Validate API readiness by checking the database, Redis, and loaded ML artifacts.

Interview talking point: the API is designed like a production recommender service. It uses precomputed artifacts for latency, Redis for performance and abuse protection, PostgreSQL for user/session state, and metrics/health checks for operability.

Quick Setup Guide
------------

### Prerequisites

- Python 3.11
- [`uv`](https://docs.astral.sh/uv/) for dependency management
- Docker and Docker Compose
- PostgreSQL for the API database
- Redis for caching, rate limiting, and integration tests
- AWS credentials only if you need DVC S3 sync, ECR image publishing, or deployment-file upload

### 1. Install dependencies

```bash
uv sync --extra test --extra pipeline
```

Use only the API dependencies when you do not need training or tests:

```bash
uv sync
```

### 2. Create local environment variables

Create a `.env` file in the project root. A minimal local setup looks like this:


### 3. Prepare ML artifacts

The inference API expects the DVC-generated artifacts to exist locally before startup:

```bash
uv run dvc pull
uv run dvc repro
```

If you only need raw data first:

```bash
uv run dvc pull data/raw/songs-info.csv
uv run dvc pull data/raw/user-info.csv
```

The serving image expects these generated files:

- `data/cleaned/songs-info-collab.csv`
- `data/processed/transformed_content_filtering.npz`
- `data/processed/track_ids.npy`
- `data/processed/collab_filtered.csv`
- `data/processed/interaction_matrix.npz`
- `data/processed/transformed_hybrid_data.npz`

### 4. Run the API locally

Start PostgreSQL and Redis, then run:

```bash
uv run python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Useful local URLs:

- Dashboard: `http://localhost:8000/dashboard`
- Health check: `http://localhost:8000/internal/health`
- Prometheus metrics: `http://localhost:8000/metrics`

### 5. Run with Docker

The compose file currently references the ECR-hosted API image and starts Redis plus Redis Exporter:

```bash
docker compose up
```

To build locally instead of pulling from ECR, build with the lowercase Dockerfile name:

```bash
docker build -f dockerfile -t pulse-play-api:local .
```

Then update `docker-compose.yaml` to use `pulse-play-api:local`, or uncomment the local `build` block.

### 6. Run tests

```bash
uv run pytest tests/api/unit -q
uv run pytest tests/api/integration -q
uv run pytest tests/recommendation-engine -q
```

Integration tests require PostgreSQL and Redis. In CI, GitHub Actions starts both services automatically.

CI/CD Pipeline
------------

The GitHub Actions workflow is defined in [`.github/workflows/CI-CD.yaml`](.github/workflows/CI-CD.yaml). It runs on pushes and pull requests to `main`.

Pipeline overview:

- **Workflow lint**: validates GitHub Actions syntax with `actionlint`.
- **Path filtering**: decides whether backend, ML, or container-related jobs need to run.
- **Model tests**: runs recommendation-engine tests when ML code or artifacts change.
- **API tests**: starts PostgreSQL and Redis services, then runs API unit and integration tests.
- **ML pipeline**: on `main`, pulls raw data from DVC remote, runs `dvc repro`, tests model behavior, and uploads generated artifacts.
- **Post-pipeline API checks**: reruns API tests after DVC artifacts are generated.
- **ECR image publish**: downloads DVC outputs, creates deployment `.env`, builds the Docker image, and pushes both SHA and `latest` tags to AWS ECR.
- **DVC artifact push**: pushes updated DVC artifacts back to the configured remote after successful checks and image publish.

Required GitHub secrets:

- `AWS_DVC_ACCESS_KEY_ID`
- `AWS_DVC_SECRET_ACCESS_KEY`
- `AWS_DOCKER_ACCESS_KEY_ID`
- `AWS_DOCKER_SECRET_ACCESS_KEY`
- `AWS_REGION`
- `ECR_REGISTRY`
- `ECR_REPOSITORY`
- `DEPLOYMENT_S3_BUCKET`
- `JWT_ACCESS_SECRET_KEY`
- `JWT_REFRESH_SECRET_KEY`
- `AWS_REDIS_URL`
- `AWS_REDIS_ADDR`
- `AWS_RDS_URL`
- `LOGIN_RATE_LIMIT`
- `LOGIN_RATE_WINDOW`
- `REFRESH_RATE_LIMIT`
- `REFRESH_RATE_WINDOW`
- `PREDICT_RATE_LIMIT`
- `PREDICT_RATE_WINDOW`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `REFRESH_TOKEN_EXPIRE_DAYS`
- `REDIS_TTL`

Deployment note: CI/CD builds and pushes the ECR image and uploads deployment files, but the current production rollout is still manual on EC2 instances in the ASG behind the ALB. CodeDeploy would be the next step for automated rolling or blue/green deployment.

Project Organization
------------

    .
    |-- backend/                         <- FastAPI application for auth, dashboard pages, inference APIs, caching, and observability.
    |   |-- api/                         <- Route handlers for auth, health checks, root/dashboard pages, and recommendation endpoints.
    |   |-- cached_recommendation/       <- Redis-backed cache helpers for recommendation responses.
    |   |-- core/                        <- Settings, database setup, security, dependencies, helpers, and rate limiting.
    |   |-- db/                          <- SQLAlchemy models for users and refresh tokens.
    |   |-- loader/                      <- Startup loaders for Redis and ML artifacts used during inference.
    |   |-- logging_fastapi/             <- API logging configuration.
    |   |-- schema/                      <- Pydantic request and response schemas.
    |   |-- static/                      <- Browser JavaScript and CSS for the recommendation dashboard.
    |   |-- templates/                   <- Jinja2 templates for landing, login, signup, and dashboard pages.
    |   |-- custom_metrics.py            <- Prometheus metrics for API, cache, search, and recommendation events.
    |   `-- main.py                      <- FastAPI app setup, lifespan startup, routers, static files, and metrics endpoint.
    |
    |-- src/                             <- Offline ML pipeline code orchestrated by DVC.
    |   |-- data/                        <- Data cleaning logic for content and collaborative catalog outputs.
    |   |-- content_based_filtering/     <- Content feature pipeline using text, categorical, and audio feature transforms.
    |   |-- collaborative_filtering/     <- Collaborative artifacts from user listening history and track-user interactions.
    |   |-- transformation/              <- Hybrid feature alignment for the collaborative-filtered catalog.
    |   `-- utils/                       <- Shared logging helpers for pipeline stages.
    |
    |-- Script/                          <- Runtime recommendation logic and evaluation scripts.
    |   |-- recommender_script.py         <- Content-based and collaborative recommendation functions used by the API.
    |   |-- hybrid_recommendation.py      <- Hybrid recommender that blends content and collaborative similarity scores.
    |   |-- evaluate.py                  <- Evaluation helper script.
    |   `-- test_hybrid.py               <- Local hybrid recommender test script.
    |
    |-- data/                            <- DVC-tracked datasets and generated pipeline artifacts.
    |   `-- raw/                         <- Raw dataset pointers tracked with DVC; actual data is stored via remote storage.
    |
    |-- models/                          <- Generated model/preprocessing artifacts such as the fitted content transformer.
    |-- notebooks/                       <- Exploratory analysis, data acquisition, and recommender experimentation notebooks.
    |-- docs/                            <- Sphinx docs and architecture diagrams for training and inference pipelines.
    |-- tests/                           <- Unit and integration tests for API routes and recommendation behavior.
    |
    |-- dvc.yaml                         <- DVC pipeline for cleaning, content filtering, collaborative filtering, and hybrid transform.
    |-- dvc.lock                         <- Locked DVC stage metadata for reproducible pipeline outputs.
    |-- dockerfile                       <- Multi-stage API image build with FastAPI and inference artifacts.
    |-- docker-compose.yaml              <- Runtime services for API, Redis, and Redis exporter.
    |-- pyproject.toml                   <- Project metadata and dependency groups for API, pipeline, dev, and test workflows.
    |-- uv.lock                          <- Locked Python dependency resolution used by uv.
    |-- Makefile                         <- Utility commands for environment setup and S3 data sync.
    |-- setup.py                         <- Package setup for importing project modules.
    |-- tox.ini                          <- Test environment configuration.
    `-- README.md                        <- Project overview and repository guide.

Component Summary
------------

- `backend` serves the production-facing FastAPI application. It handles authentication, recommendation API calls, Redis caching, rate limiting, health checks, static dashboard assets, and Prometheus metrics.
- `src` contains the offline ML pipeline. DVC runs these stages to clean raw data, create content features, generate collaborative filtering artifacts, and align the hybrid feature matrix.
- `Script` contains inference-time recommendation logic imported by the API routes. It computes content, collaborative, and hybrid recommendations from precomputed artifacts.
- `data` and `models` store DVC-managed datasets and generated artifacts. Raw data is referenced through `.dvc` pointer files, while processed matrices and transformers are produced by the pipeline.
- `docs` contains documentation and architecture diagrams, including the ML training and inference pipeline diagrams.
- `tests` covers API auth, health, recommendation routes, integration flows, and recommender behavior.
- `dockerfile` and `docker-compose.yaml` define how the service is packaged and run with Redis. The compose file references the API image hosted in AWS ECR.
- `dvc.yaml` is the source of truth for the non-linear ML training graph: content and collaborative branches both feed the final hybrid artifact generation.

--------

<p><small>Project based on the <a target="_blank" href="https://drivendata.github.io/cookiecutter-data-science/">cookiecutter data science project template</a>. #cookiecutterdatascience</small></p>
