# Use an official Python runtime as a parent image
# FROM python:3.14-slim as builder
#
# # Poetry environment variables
# ENV POETRY_NO_INTERACTION=1 \
#   POETRY_VIRTUALENVS_IN_PROJECT=1 \
#   POETRY_VIRTUALENVS_CREATE=1 \
#   POETRY_CACHE_DIR_WORKER=/tmp/poetry_cache/worker
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
# RUN --mount=type=cache,target=$POETRY_CACHE_DIR_WORKER \
#   poetry install --only main --no-root
#
# # Stage 2: Runtime
# FROM python:3.14-slim AS runtime
#
# WORKDIR /app
#
# # Install system dependencies for pyodbc
# RUN apt-get update && apt-get install -y --no-install-recommends \
#   unixodbc \
#   && rm -rf /var/lib/apt/lists/*
#
# ENV PYTHONUNBUFFERED=1 \
#   PATH="/app/.venv/bin:$PATH"
#
# # Copy the virtual environment from the builder
# COPY --from=builder /app/.venv /app/.venv
#
# # Copy your source code (will be owned by root by default)
# COPY ./src ./src
#
# # Ensure the logs directory exists
# RUN mkdir -p /app/logs
#
# # Use exec form to ensure SIGTERM signals reach your consumer for graceful shutdown
# CMD ["python", "src/main.py"]


# --- Stage 1: Builder ---
FROM python:3.14-slim AS builder

# Copy uv from the official image (fastest & lightest)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# uv environment variables
ENV UV_COMPILE_BYTECODE=1 \
  UV_LINK_MODE=copy

WORKDIR /app

# Install dependencies first (leverages Docker cache)
# --frozen: ignores lockfile updates
# --no-install-project: skips installing your source code package for better caching
RUN --mount=type=cache,target=/root/.cache/uv \
  --mount=type=bind,source=uv.lock,target=uv.lock \
  --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
  uv sync --frozen --no-install-project --no-dev

# --- Stage 2: Runtime ---
FROM python:3.14-slim AS runtime

WORKDIR /app

# Install system dependencies for pyodbc
RUN apt-get update && apt-get install -y --no-install-recommends \
  unixodbc \
  && rm -rf /var/lib/apt/lists/*

# Set standard environment variables
ENV PYTHONUNBUFFERED=1 \
  PATH="/app/.venv/bin:$PATH"

# Copy the pre-built virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy source and setup logs
COPY ./src ./src
RUN mkdir -p /app/logs

# Use exec form for SIGTERM handling
CMD ["python", "src/main.py"]
