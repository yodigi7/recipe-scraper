# # Use an official Python runtime as a parent image
# FROM python:3.14-slim as builder
#
# # Poetry environment variables
# ENV POETRY_NO_INTERACTION=1 \
#   POETRY_VIRTUALENVS_IN_PROJECT=1 \
#   POETRY_VIRTUALENVS_CREATE=1 \
#   POETRY_CACHE_DIR_PROD=/tmp/poetry_cache/producer
#
# WORKDIR /app
#
# # Install poetry (pinning version for consistency)
# RUN pip install poetry==2.3
#
# # Copy only dependency files first to leverage Docker cache
# COPY pyproject.toml poetry.lock ./
#
# # Install main dependencies only (no dev tools, no root package yet)
# RUN --mount=type=cache,target=$POETRY_CACHE_DIR_PROD \
#   poetry install --only main --no-root
#
# # Stage 2: Runtime
# FROM python:3.14-slim AS runtime
#
# WORKDIR /app
#
# ENV PYTHONUNBUFFERED=1 \
#   PATH="/app/.venv/bin:$PATH"
#
# # Copy the virtual environment from the builder
# COPY --from=builder /app/.venv /app/.venv
#
# # Copy your source code (will be owned by root by default)
# COPY . .
#
# # Use exec form to ensure SIGTERM signals reach your consumer for graceful shutdown
# CMD ["python", "main.py"]
#
# FROM python:3.14-slim
#
# # 1. Prevent Poetry from creating virtualenvs (critical for Docker)
# ENV POETRY_VIRTUALENVS_CREATE=false \
#   POETRY_NO_INTERACTION=1 \
#   PYTHONUNBUFFERED=1
#
# WORKDIR /app
#
# # 2. Install Poetry
# RUN pip install --no-cache-dir poetry==2.3
#
# # 3. Copy only dependency files first (optimizes Docker caching)
# COPY pyproject.toml poetry.lock ./
#
# # 4. Install dependencies only (skip root package install for now)
# RUN poetry install --no-root --no-directory
#
# # 5. Copy your script and run
# COPY . .
# CMD ["python", "main.py"]
FROM python:3.14-slim-bookworm

# 1. Install uv using the official installer script
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 2. Set environment variables
# - UV_COMPILE_BYTECODE: Compiles to .pyc for faster startup
# - PYTHONUNBUFFERED: Standard for logging in Docker
ENV UV_COMPILE_BYTECODE=1 \
  PYTHONUNBUFFERED=1

WORKDIR /app

# 3. Install dependencies 
# We use a cache mount to speed up subsequent builds significantly
RUN --mount=type=cache,target=/root/.cache/uv \
  --mount=type=bind,source=uv.lock,target=uv.lock \
  --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
  uv sync --frozen --no-install-project --no-dev

# 4. Copy the application code
COPY . .

# 5. Run the application
# Use 'uv run' to ensure the environment is correctly activated
CMD ["uv", "run", "main.py"]
