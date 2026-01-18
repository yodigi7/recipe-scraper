from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict


@dataclass
class UrlStatus:
    url: str
    last_modified: datetime | None = None


@dataclass
class Recipe:
    canonical_url: str
    json: Dict[str, Any] | None
    last_scraped: datetime | None
