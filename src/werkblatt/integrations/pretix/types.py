from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ExternalWorkshop:
    reference: str
    title: str
    starts_at: datetime
    ends_at: datetime | None
    location: str
    event_slug: str = ""


@dataclass(frozen=True)
class ExternalRegistration:
    reference: str
    display_name: str
