from dataclasses import replace
from datetime import date, datetime
from typing import Any
from urllib.parse import quote

from .client import PretixClient
from .types import ExternalRegistration, ExternalWorkshop, ExternalWorkshopBatch


def translated(value: Any, language: str = "de") -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        preferred = value.get(language) or value.get("en")
        if isinstance(preferred, str):
            return preferred
        return next((item for item in value.values() if isinstance(item, str)), "")
    return ""


def parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class PretixWorkshopProvider:
    def __init__(self, client: PretixClient, organizer: str):
        if not organizer or not all(char.isalnum() or char in "-_" for char in organizer):
            raise ValueError("Invalid Pretix organizer")
        self.client = client
        self.organizer = quote(organizer, safe="")

    def list_workshops(
        self,
        *,
        include_testmode: bool = False,
        not_before: date | None = None,
        excluded_event_slugs: frozenset[str] = frozenset(),
    ) -> list[ExternalWorkshop]:
        batch = self.list_workshop_batch(
            include_testmode=include_testmode,
            not_before=not_before,
            excluded_event_slugs=excluded_event_slugs,
        )
        return [workshop for workshop in batch.workshops if workshop.active]

    def list_workshop_batch(
        self,
        *,
        include_testmode: bool = False,
        not_before: date | None = None,
        excluded_event_slugs: frozenset[str] = frozenset(),
    ) -> ExternalWorkshopBatch:
        workshops: list[ExternalWorkshop] = []
        synchronized_event_slugs: set[str] = set()
        ignored_event_slugs: set[str] = set()
        event_path = f"/api/v1/organizers/{self.organizer}/events/"
        for event in self.client.pages(event_path):
            event_slug = str(event.get("slug", "")).strip()
            if not event_slug:
                continue
            if event_slug in excluded_event_slugs or (
                event.get("testmode") is True and not include_testmode
            ):
                ignored_event_slugs.add(event_slug)
                continue
            synchronized_event_slugs.add(event_slug)
            event_active = event.get("live") is True
            escaped_event_slug = quote(event_slug, safe="")
            if event.get("has_subevents") is True:
                subevent_path = (
                    f"/api/v1/organizers/{self.organizer}/events/{escaped_event_slug}/subevents/"
                )
                params = {"date_from_after": not_before.isoformat()} if not_before else None
                for item in self.client.pages(subevent_path, params):
                    workshop = self._map_workshop(event_slug, event, item)
                    if workshop is not None and (
                        not_before is None or workshop.starts_at.date() >= not_before
                    ):
                        workshops.append(
                            replace(
                                workshop,
                                active=event_active
                                and item.get("active") is True
                                and item.get("is_public", True) is True,
                            )
                        )
            else:
                workshop = self._map_workshop(event_slug, event, event)
                if workshop is not None and (
                    not_before is None or workshop.starts_at.date() >= not_before
                ):
                    workshops.append(replace(workshop, active=event_active))
        return ExternalWorkshopBatch(
            workshops=tuple(sorted(workshops, key=lambda item: item.starts_at)),
            synchronized_event_slugs=frozenset(synchronized_event_slugs),
            ignored_event_slugs=frozenset(ignored_event_slugs),
        )

    def list_registrations(
        self, event_slug: str, subevent_id: int | None = None
    ) -> list[ExternalRegistration]:
        event = quote(event_slug, safe="")
        path = f"/api/v1/organizers/{self.organizer}/events/{event}/orders/"
        params = {"status": "p"}
        if subevent_id is not None:
            params["subevent"] = str(subevent_id)
        registrations: list[ExternalRegistration] = []
        for order in self.client.pages(path, params):
            code = str(order.get("code", ""))
            for position in (
                order.get("positions", []) if isinstance(order.get("positions"), list) else []
            ):
                if not isinstance(position, dict) or position.get("canceled") is True:
                    continue
                name = " ".join(
                    filter(
                        None,
                        [
                            str(position.get("attendee_name_parts", {}).get("given_name", "")),
                            str(position.get("attendee_name_parts", {}).get("family_name", "")),
                        ],
                    )
                ).strip()
                if not name:
                    name = str(position.get("attendee_name") or "")
                reference = f"{code}:{position.get('id', '')}"
                if name and code:
                    registrations.append(
                        ExternalRegistration(reference=reference, display_name=name)
                    )
        return registrations

    @staticmethod
    def _map_workshop(
        event_slug: str, event: dict[str, Any], item: dict[str, Any]
    ) -> ExternalWorkshop | None:
        starts_at = parse_time(item.get("date_from"))
        if starts_at is None:
            return None
        subevent_id = item.get("id") if item is not event else None
        reference = f"{event_slug}:{subevent_id}" if subevent_id is not None else event_slug
        return ExternalWorkshop(
            reference=reference,
            event_slug=event_slug,
            title=translated(item.get("name") or event.get("name") or event_slug),
            starts_at=starts_at,
            ends_at=parse_time(item.get("date_to")),
            location=translated(item.get("location") or event.get("location") or ""),
        )
