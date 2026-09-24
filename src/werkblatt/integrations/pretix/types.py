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
    active: bool = True


@dataclass(frozen=True)
class ExternalWorkshopBatch:
    workshops: tuple[ExternalWorkshop, ...]
    synchronized_event_slugs: frozenset[str]
    ignored_event_slugs: frozenset[str]


@dataclass(frozen=True)
class ExternalRegistration:
    reference: str
    display_name: str
