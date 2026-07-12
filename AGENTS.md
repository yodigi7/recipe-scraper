# recipe-scraper — Agent Guide

## Project Overview

Recipe scraper microservice system: a **producer** loads sitemaps from 5 recipe websites, publishes URLs to RabbitMQ queues; a **worker** consumes those URLs, scrapes recipe data via `recipe-scrapers` library, and upserts to PostgreSQL.

Architecture: `producer` -> `RabbitMQ` -> `worker` -> `PostgreSQL`

## Directory Structure

```
recipe-scraper/
├── docker-compose.yml          # 4 services: db, rabbitmq, producer, worker
├── .gitignore
├── .pre-commit-config.yaml     # black 25.1.0, isort 7.0.0, pre-commit-hooks
├── AGENTS.md                   # this file
├── CODE_REVIEW.md              # prior review notes
│
├── producer/                   # Sitemap fetcher + RabbitMQ publisher
│   ├── Dockerfile              # uv-based, python:3.14-slim-bookworm
│   ├── pyproject.toml          # httpx, tenacity, lxml, aio-pika
│   ├── pyrightconfig.json
│   ├── .dockerignore
│   ├── uv.lock
│   ├── main.py                 # entrypoint: connect RabbitMQ, load sitemaps, publish
│   ├── scraper.py              # SitemapLoader protocol + 5 site loaders, get_webpage()
│   ├── models.py               # UrlStatus dataclass (NO sqlmodel Recipe here)
│   ├── db.py                   # PostgreSQL engine + session factory
│   └── errors.py               # NotOKHttpResponse
│
└── worker/                     # RabbitMQ consumer + recipe scraper + DB writer
    ├── Dockerfile              # multi-stage, uv sync + unixodbc
    ├── pyproject.toml          # httpx, recipe-scrapers, sqlmodel, pyodbc, anyio
    ├── pyrightconfig.json
    ├── uv.lock
    ├── README.md               # (empty)
    └── src/
        ├── main.py             # entrypoint: connect RabbitMQ, consume 5 queues
        ├── scraper.py          # scrape_recipe(), get_webpage(), load_sitemap()
        ├── models.py           # Recipe SQLModel table (Postgres)
        ├── domain_models.py    # UrlStatus + Recipe pure dataclasses (no SQL)
        ├── db.py               # Postgres engine + session + init_db() + version hooks
        ├── utils.py            # map_recipe_for_db(), upsert_to_db() with retry
        ├── core.py             # Config dataclass, logging setup
        ├── constants.py        # SCRAPE_SLEEP = 2
        └── errors.py           # NotOKHttpResponse
```

## How to Run

```sh
docker compose up --build
```

Or run individual tasks:

```sh
# Run linter (both services)
cd producer && uv run lint
cd worker && uv run lint

# Run formatter
cd worker && uv run fmt

# Run tests
cd worker && uv run test
```

Access RabbitMQ UI at http://localhost:15672/ (guest/guest).

## Key Details for Agents

### Services

| Service | Image | Entrypoint | Depends on |
|---------|-------|------------|------------|
| `db` | pgvector/pgvector:pg18-trixie | — | — |
| `rabbitmq` | rabbitmq:4.2-management | — | — |
| `producer` | build: ./producer | `uv run main.py` | rabbitmq (healthy) |
| `worker` | build: ./worker | `python src/main.py` | rabbitmq, db |

### Connection Strings (all hardcoded — use env vars in production)

- **PostgreSQL**: `postgresql+psycopg2://user:password@db:5432/recipes_db`
- **RabbitMQ**: host=`rabbitmq`, port=`5672`, login=`guest`, password=`guest`

### Sitemap Loaders (producer/scraper.py)

Each implements `SitemapLoader` protocol with `queue_name`, `sitemaps`, `load_sitemap()`:

| Loader | Queue Name | Sitemap URLs | Has lastmod? |
|--------|-----------|--------------|--------------|
| `AllRecipesSitemapLoader` | `all_recipes` | sitemap_1..4.xml | Yes |
| `BudgetBytesSitemapLoader` | `budget_bytes` | post-sitemap, post-sitemap2 | Yes |
| `HelloFreshSitemapLoader` | `hello_fresh` | sitemap_recipe_pages.xml | Yes |
| `SeriousEatsSitemapLoader` | `serious_eats` | sitemap_1.xml | Yes |
| `BlueApronSitemapLoader` | `blue_apron` | recipes/sitemap.xml | No — uses current time |

### RabbitMQ Architecture

- 5 **durable queues**: `all_recipes`, `budget_bytes`, `hello_fresh`, `serious_eats`, `blue_apron`
- Each queue has a **DLX/DLQ** pair: `{queue}.dlx` exchange + `{queue}.dlq` queue
- Messages are published to the default exchange with `routing_key = queue_name`
- Worker uses `prefetch_count=1` (process one message at a time)
- Messages are **not re-queued** on failure (dead-lettered instead)

### Producer Flow (producer/main.py:load_recipes)

1. Creates RabbitMQ channel + DLX/DLQ
2. For each sitemap URL:
   - Fetches XML via `get_webpage()` (retry 3x, exponential jitter)
   - Parses via `sitemap_loader.load_sitemap()`
   - Queries DB for existing URLs to check `last_modified` vs `last_scraped`
   - Publishes URLs needing update to the queue (PERSISTENT delivery)
3. Awaits all publish tasks via `asyncio.gather()`

**Currently only `BlueApronSitemapLoader` is active** (others commented out in main.py).

### Worker Flow (worker/src/main.py:scrape_url → utils.py:upsert_to_db)

1. `on_message()` receives URL from queue, calls `scrape_url()`
2. `scrape_url()` → `scrape_recipe()` → fetches webpage + `scrape_html()` → domain `Recipe`
3. `map_recipe_for_db()` → SQLModel `Recipe`
4. `upsert_to_db()` → try INSERT, on `IntegrityError` rollback + UPDATE (retry 3x)
5. Sleeps `SCRAPE_SLEEP` (2s) between scrapes

### Database Schema (both producer/models.py holds a pure dataclass; actual SQLModel Recipe is in worker/src/models.py)

**Note**: `producer/models.py` only has the `UrlStatus` dataclass. The SQLModel `Recipe` table is defined in `worker/src/models.py`.

`Recipe` table (SQLModel):
- `recipe_id`: int, PK (serial)
- `canonical_url`: String, not null
- `json_data`: JSONB, nullable
- `json_hash`: BYTEA, computed `digest(json_data::text, 'sha256')`, **unique**, persisted
- `last_updated`: DateTime(tz), server_default=CURRENT_TIMESTAMP
- `last_scraped`: DateTime(tz)
- `version`: String(15)
- `url_hash`: BYTEA, computed `digest(canonical_url, 'sha256')`, **unique**, persisted
- Index: `IX_recipe_url_hash` on `url_hash`

`init_db()` in `worker/src/db.py` enables the `pgcrypto` extension (required for `digest()`) and creates all tables.

### Error Handling

- **HTTP retries**: `@tenacity.retry` with exponential jitter (3s base, 3x exp, 3s jitter)
  - Producer: 3 attempts, retries only `NotOKHttpResponse`
  - Worker: 2 attempts for `get_webpage()`
- **DB upsert retries**: `upsert_to_db()` retries 3x on any exception
- **RabbitMQ connection**: 30 attempts with 5s sleep, then exits
- **DB session errors**: caught, logged, session rolled back
- **Dead-letter queues**: failed messages go to `{queue}.dlq` via DLX

### Dependencies

**Producer** (`producer/pyproject.toml`):
httpx, tenacity, lxml, aio-pika, sqlmodel, psycopg2-binary

**Worker** (`worker/pyproject.toml`):
httpx, recipe-scrapers, sqlmodel, pyodbc, azure-identity, tenacity, psycopg2-binary, aio-pika, anyio

### Package Manager

Both services use **uv** (`uv sync`, `uv run`). Lock files: `producer/uv.lock`, `worker/uv.lock`.

### Linting/Formatting/Tests

- **Ruff** replaces black + isort (single tool, fast). Config in each `pyproject.toml` under `[tool.ruff]`.
- Pre-commit hooks run `ruff check --fix` and `ruff-format`.
- Worker has pytest tests in `worker/tests/`. Run with `cd worker && uv run test`.
- Common commands:

  | Command | What it does |
  |---------|-------------|
  | `uv run lint` | Ruff check (no changes) |
  | `uv run fmt` | Ruff format in-place |
  | `uv run fmt-check` | Check formatting (CI-friendly) |
  | `uv run test` | Run pytest suite (worker only) |

- Pyright config in both producer/ and worker/ (points to `.venv`).

### Agent Workflow Tips

1. **Adding a new sitemap source**: Add a new loader class in `producer/scraper.py` implementing `SitemapLoader`, add its queue name to `worker/src/main.py:queues`, and call `load_recipes()` in `producer/main.py`.
2. **Changes to DB schema**: Update `worker/src/models.py` Recipe table and potentially `producer/db.py` query logic.
3. **Testing locally**: Run `docker compose up --build`. The worker logs to both console and `/app/logs/logging.txt`.
4. **Secrets**: Currently hardcoded. Move to environment variables / `.env` file for production.
5. **The producer and worker share the same RabbitMQ and DB credentials** — updates must stay in sync.
6. **Pre-commit hooks use Ruff**. After adding Ruff dep, run `uv sync` then `pre-commit install` in each service.
7. **Secrets are mirrored** in `.env`, `docker-compose.yml`, and `producer/db.py`/`worker/src/db.py` — change all four when rotating credentials.
