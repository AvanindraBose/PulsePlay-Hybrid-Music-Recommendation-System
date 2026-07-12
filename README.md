Pulse Play Hybrid Music Recommendation System
==============================

Creating a Hybrid Music Recommendation System.

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
