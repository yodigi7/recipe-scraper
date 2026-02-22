import datetime
from dataclasses import dataclass
from typing import Any, Dict

from pydantic import ConfigDict, model_validator
from sqlalchemy import Computed, Index, text, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB, BYTEA
from sqlmodel import Column, Field, SQLModel, FetchedValue


class Recipe(SQLModel, table=True):
    # 1. Primary Key: PostgreSQL handles this automatically as SERIAL/IDENTITY
    recipe_id: int | None = Field(default=None, primary_key=True)

    # 2. VARCHAR(MAX) -> String: In Postgres, String/TEXT has no performance penalty
    canonical_url: str = Field(sa_column=Column(String, nullable=False))

    # 3. JSON -> JSONB: JSONB is the 2026 standard for optimized reads and indexing
    json_data: Dict[str, Any] | None = Field(
        default_factory=dict, sa_column=Column(JSONB, nullable=True)
    )

    # 4. VARBINARY -> BYTEA: Use sha256() for binary hashing
    # Note: sha256() requires casting the JSONB to text, then to bytea
    json_hash: bytes | None = Field(
        default=None,
        sa_column=Column(
            BYTEA,
            Computed(
                "CASE WHEN json_data IS NULL THEN NULL "
                "ELSE digest(json_data::text, 'sha256') END",
                persisted=True,
            ),
            nullable=True,
            unique=True,
        ),
    )

    # 5. DATETIME2 -> DateTime: Best practice for 2026 is timezone-aware
    last_updated: datetime.datetime | None = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=text("CURRENT_TIMESTAMP"),
            nullable=True,
        )
    )

    last_scraped: datetime.datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    version: str = Field(sa_column=Column(String(15)))

    # 6. Binary Hash for URL
    url_hash: bytes | None = Field(
        sa_column=Column(
            BYTEA,
            Computed("digest(canonical_url, 'sha256')", persisted=True),
            nullable=True,
            unique=True,  # Ensures PostgreSQL uses a B-tree unique index
        ),
    )

    __table_args__ = (Index("IX_recipe_url_hash", "url_hash"),)
