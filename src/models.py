import datetime
from dataclasses import dataclass
from typing import Any, Dict

from pydantic import ConfigDict, model_validator
from sqlalchemy import Computed, Index, text
from sqlalchemy.dialects.mssql import DATETIME2, JSON, VARBINARY, VARCHAR
from sqlmodel import Column, Field, SQLModel


class Recipe(SQLModel, table=True):
    # Surrogate primary key
    recipe_id: int | None = Field(default=None, primary_key=True)

    # Full URL retained; cannot be UNIQUE as MAX in SQL Server
    canonical_url: str = Field(sa_column=Column(VARCHAR("max"), nullable=False))

    # Store JSON text in NVARCHAR(MAX); SQL Server has JSON functions over NVARCHAR
    json: Dict[str, Any] | None = Field(default_factory=dict, sa_column=Column(JSON, nullable=True))

    # Binary SHA-256 of json text; keep NULL if json is NULL
    json_hash: bytes | None = Field(
        default=None,
        sa_column=Column(
            VARBINARY(32),
            Computed("CASE WHEN json IS NULL THEN NULL ELSE HASHBYTES('SHA2_256', json) END", persisted=True),
            nullable=True,
        ),
    )

    # Prefer DATETIME2 for precision and range
    last_updated: datetime.datetime | None = Field(
        sa_column=Column(DATETIME2(0), server_default=text("SYSUTCDATETIME()"), nullable=True)
    )
    last_scraped: datetime.datetime | None = Field(sa_column=Column(DATETIME2(precision=0), nullable=True))

    version: str = Field(sa_column=Column(VARCHAR(15)))

    # Binary SHA-256 of canonical_url
    url_hash: bytes | None = Field(
        default=None,
        sa_column=Column(
            VARBINARY(32), Computed("HASHBYTES('SHA2_256', canonical_url)", persisted=True), nullable=True, unique=True
        ),
    )

    # Example index on the hash for point lookups
    __table_args__ = (Index("IX_recipe_url_hash", "url_hash"),)
