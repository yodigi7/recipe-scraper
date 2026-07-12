# Recipe Scraper

A microservice system that scrapes recipe websites. A **producer** loads sitemaps from 5 recipe sites and publishes URLs to RabbitMQ queues. A **worker** consumes those URLs, scrapes recipe data via the `recipe-scrapers` library, and stores it in PostgreSQL.

Architecture: `producer` → `RabbitMQ` → `worker` → `PostgreSQL`

---

## Quick Start

```sh
docker compose up --build
```

This starts all 4 services: PostgreSQL, RabbitMQ, producer, and worker.

### Access Points

| Service | URL |
|---------|-----|
| RabbitMQ UI | http://localhost:15672/ (guest/guest) |
| PostgreSQL | localhost:5432 (user/password) |

---

## Project Structure

```
recipe-scraper/
├── docker-compose.yml          # All 4 services configured here
├── .env                        # Local secrets (gitignored)
├── .env.example                # Template for .env
├── AGENTS.md                   # Full dev reference for AI agents
│
├── producer/                   # Sitemap loader + RabbitMQ publisher
│   ├── main.py                 # Entrypoint — connects RabbitMQ, loads sitemaps
│   ├── scraper.py              # SitemapLoader protocol + 5 site loaders
│   ├── models.py               # UrlStatus dataclass
│   ├── db.py                   # PostgreSQL engine + session factory
│   └── errors.py               # NotOKHttpResponse
│
├── worker/                     # RabbitMQ consumer + recipe scraper
│   └── src/
│       ├── main.py             # Entrypoint — consumes 5 queues
│       ├── scraper.py          # scrape_recipe() via recipe-scrapers library
│       ├── models.py           # Recipe SQLModel table (DB schema)
│       ├── domain_models.py    # Pure dataclasses (no SQL binding)
│       ├── utils.py            # map_recipe_for_db() + upsert_to_db()
│       ├── db.py               # Postgres engine + init_db()
│       ├── core.py             # Config + logging setup
│       ├── constants.py        # SCRAPE_SLEEP = 2
│       └── errors.py           # NotOKHttpResponse
```

---

## How It Works

### Producer (`producer/main.py`)

1. Connects to RabbitMQ (retries up to 30 times)
2. For each sitemap URL defined by the loader:
   - Fetches the sitemap XML
   - Parses recipe URLs and their `last_modified` timestamps
   - Queries PostgreSQL to check which URLs are outdated or new
   - Publishes only URLs needing an update to RabbitMQ
3. **Currently only BlueApron is enabled** — other loaders are commented out in `main.py`

### Worker (`worker/src/main.py`)

1. Listens on 5 RabbitMQ queues (one per site)
2. For each URL received:
   - Fetches the webpage via httpx
   - Scrapes recipe data using `recipe-scrapers`
   - Converts the result to the DB model
   - Upserts to PostgreSQL (INSERT, falls back to UPDATE on conflict)
   - Sleeps 2 seconds between scrapes to avoid rate limiting
3. Failed messages go to dead-letter queues (DLQ) instead of being re-queued

### Database

PostgreSQL with `pgcrypto` extension. The `Recipe` table uses computed SHA-256 columns (`url_hash`, `json_hash`) with unique constraints for deduplication.

---

## Individual Commands

Run these from the `producer/` or `worker/` directory:

```sh
uv run lint        # Ruff check (no changes)
uv run fmt         # Ruff format in-place
uv run fmt-check   # Check formatting (CI-friendly)
```

Worker only:
```sh
uv run test        # Run pytest suite
```

---

## Sitemap Sources

| Site | Queue | Has lastmod? |
|------|-------|-------------|
| allrecipes.com | all_recipes | Yes |
| budgetbytes.com | budget_bytes | Yes |
| hellofresh.com | hello_fresh | Yes |
| seriouseats.com | serious_eats | Yes |
| blueapron.com | blue_apron | No (uses current time) |

---

## Logging

The worker logs to both console (INFO+) and `/app/logs/logging.txt` (DEBUG+). Logs are rotated at 10 MB, keeping 3 backups. The `logs/` directory is synced to the host via Docker volume (`./logs`).

---

## Configuration

Secrets are currently hardcoded in `docker-compose.yml`, `producer/db.py`, and `worker/src/db.py`. For production, they should be moved to environment variables (see `.env.example`).

---

## Tech Stack

- **Python 3.14** (producer) / **3.13+** (worker)
- **uv** package manager
- **RabbitMQ** via aio-pika (async AMQP)
- **PostgreSQL 18** with pgvector extension
- **SQLModel** + SQLAlchemy (ORM)
- **httpx** (async HTTP client)
- **recipe-scrapers** (parsing library)
- **ruff** (linting + formatting)
- **pytest** (testing)
