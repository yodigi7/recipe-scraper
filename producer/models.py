from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Column, Computed, DateTime, String
from sqlalchemy.dialects.postgresql import BYTEA
from sqlmodel import Field, SQLModel


@dataclass
class UrlStatus:
    url: str
    last_modified: datetime | None = None


class Recipe(SQLModel, table=True):
    recipe_id: int | None = Field(default=None, primary_key=True)
    canonical_url: str = Field(sa_column=Column(String, nullable=False))
    last_scraped: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    url_hash: bytes | None = Field(
        sa_column=Column(
            BYTEA,
            Computed("digest(canonical_url, 'sha256')", persisted=True),
            nullable=True,
            unique=True,
        )
    )
