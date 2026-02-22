from dataclasses import dataclass
from datetime import datetime


@dataclass
class UrlStatus:
    url: str
    last_modified: datetime | None = None
