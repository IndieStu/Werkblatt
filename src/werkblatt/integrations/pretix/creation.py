import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import quote

from .client import PretixClient, PretixUnavailable


def _valid_slug(value: str) -> bool:
    return bool(value) and all(
        character.isascii() and (character.isalnum() or character in "-_") for character in value
    )


def numbered_event_slug(title: str, existing_slugs: set[str]) -> str:
    normalized = unicodedata.normalize("NFKD", title)
    ascii_title = normalized.encode("ascii", "ignore").decode("ascii").lower()
    base = re.sub(r"[^a-z0-9]+", "-", ascii_title).strip("-") or "workshop"
    base = base[:72].rstrip("-") or "workshop"
    pattern = re.compile(rf"^{re.escape(base)}-(\d+)$")
    used_numbers = {
        int(match.group(1))
        for slug in existing_slugs
        if (match := pattern.fullmatch(slug)) is not None
    }
    number = max(used_numbers, default=0) + 1
    return f"{base}-{number}"


@dataclass(frozen=True)
class PretixEventDraft:
    slug: str
    title: str
    starts_at: datetime
    ends_at: datetime | None
    location: str
    capacity: int
    child_registration_enabled: bool

    def __post_init__(self) -> None:
        if not _valid_slug(self.slug):
            raise ValueError("Invalid Pretix event slug")
        if not self.title.strip():
            raise ValueError("Pretix event title is required")
        if self.starts_at.utcoffset() is None:
            raise ValueError("Pretix event start must include a timezone")
        if self.ends_at is not None and self.ends_at.utcoffset() is None:
            raise ValueError("Pretix event end must include a timezone")
        if self.ends_at is not None and self.ends_at <= self.starts_at:
            raise ValueError("Pretix event end must be after its start")
        if self.capacity < 1:
            raise ValueError("Pretix event capacity must be positive")


@dataclass(frozen=True)
class PretixCreationPreset:
    template_event_slug: str
    primary_item_internal_name: str
    child_item_internal_name: str

    def __post_init__(self) -> None:
        if not _valid_slug(self.template_event_slug):
            raise ValueError("Invalid Pretix template event slug")
        if not self.primary_item_internal_name.strip():
            raise ValueError("Primary Pretix item internal name is required")
        if not self.child_item_internal_name.strip():
            raise ValueError("Child Pretix item internal name is required")
        if self.primary_item_internal_name == self.child_item_internal_name:
            raise ValueError("Pretix item internal names must be distinct")


@dataclass(frozen=True)
class CreatedPretixEvent:
    slug: str
    public_url: str
    live: bool
    is_public: bool


@dataclass(frozen=True)
class PretixTemplateInspection:
    event_slug: str
    primary_item_internal_name: str
    child_item_internal_name: str
    capacity: int | None


class PretixEventCreator:
    def __init__(self, client: PretixClient, organizer: str):
        if not _valid_slug(organizer):
            raise ValueError("Invalid Pretix organizer")
        self.client = client
        self.organizer = quote(organizer, safe="")

    def create_from_template(
        self, *, draft: PretixEventDraft, preset: PretixCreationPreset
    ) -> CreatedPretixEvent:
        event_path = f"/api/v1/organizers/{self.organizer}/events/"
        self.inspect_template(preset)
        payload = {
            "name": {"de": draft.title.strip()},
            "slug": draft.slug,
            "live": False,
            "testmode": False,
            "currency": "EUR",
            "date_from": draft.starts_at.isoformat(),
            "date_to": draft.ends_at.isoformat() if draft.ends_at else None,
            "date_admission": None,
            "is_public": False,
            "presale_start": None,
            "presale_end": None,
            "location": {"de": draft.location.strip()} if draft.location.strip() else None,
            "geo_lat": None,
            "geo_lon": None,
            "seating_plan": None,
            "seat_category_mapping": {},
            "has_subevents": False,
            "meta_data": {},
            "timezone": "Europe/Berlin",
            "item_meta_properties": {},
            "all_sales_channels": True,
            "limit_sales_channels": [],
        }
        event = self.client.post(
            event_path,
            payload,
            params={"clone_from": preset.template_event_slug},
        )
        escaped_slug = quote(draft.slug, safe="")
        base_path = f"/api/v1/organizers/{self.organizer}/events/{escaped_slug}"
        items = list(self.client.pages(base_path + "/items/"))
        primary = self._item_by_internal_name(items, preset.primary_item_internal_name)
        child = self._item_by_internal_name(items, preset.child_item_internal_name)
        quotas = list(self.client.pages(base_path + "/quotas/"))
        capacity_quota = self._capacity_quota(quotas, int(primary["id"]), int(child["id"]))

        updated_child = self.client.patch(
            base_path + f"/items/{int(child['id'])}/",
            {"active": draft.child_registration_enabled},
        )
        if updated_child.get("active") is not draft.child_registration_enabled:
            raise PretixUnavailable("Pretix did not apply the child registration setting")
        updated_quota = self.client.patch(
            base_path + f"/quotas/{int(capacity_quota['id'])}/",
            {"size": draft.capacity},
        )
        if updated_quota.get("size") != draft.capacity:
            raise PretixUnavailable("Pretix did not apply the workshop capacity")
        verified = self.client.get(base_path + "/")
        if verified.get("slug") != draft.slug:
            raise PretixUnavailable("Pretix returned an unexpected event reference")
        if verified.get("live") is not False or verified.get("is_public") is not False:
            raise PretixUnavailable("Pretix created an event in an unsafe publication state")
        return CreatedPretixEvent(
            slug=str(verified.get("slug") or event.get("slug") or ""),
            public_url=str(verified.get("public_url") or event.get("public_url") or ""),
            live=False,
            is_public=False,
        )

    def inspect_template(self, preset: PretixCreationPreset) -> PretixTemplateInspection:
        template_slug = quote(preset.template_event_slug, safe="")
        template_path = f"/api/v1/organizers/{self.organizer}/events/{template_slug}"
        event = self.client.get(template_path + "/")
        if event.get("live") is not False or event.get("is_public") is not False:
            raise PretixUnavailable("Pretix template is not safely hidden")
        items = list(self.client.pages(template_path + "/items/"))
        primary = self._item_by_internal_name(items, preset.primary_item_internal_name)
        child = self._item_by_internal_name(items, preset.child_item_internal_name)
        quotas = list(self.client.pages(template_path + "/quotas/"))
        capacity_quota = self._capacity_quota(quotas, int(primary["id"]), int(child["id"]))
        capacity = capacity_quota.get("size")
        if capacity is not None and not isinstance(capacity, int):
            raise PretixUnavailable("Pretix template quota has an invalid capacity")
        return PretixTemplateInspection(
            event_slug=str(event.get("slug") or preset.template_event_slug),
            primary_item_internal_name=preset.primary_item_internal_name,
            child_item_internal_name=preset.child_item_internal_name,
            capacity=capacity,
        )

    @staticmethod
    def _item_by_internal_name(items: list[dict[str, Any]], internal_name: str) -> dict[str, Any]:
        matches = [item for item in items if item.get("internal_name") == internal_name]
        if len(matches) != 1 or not isinstance(matches[0].get("id"), int):
            raise PretixUnavailable("Pretix template item mapping is incomplete or ambiguous")
        return matches[0]

    @staticmethod
    def _capacity_quota(
        quotas: list[dict[str, Any]], primary_item_id: int, child_item_id: int
    ) -> dict[str, Any]:
        matches = []
        for quota in quotas:
            item_ids = quota.get("items")
            if (
                isinstance(item_ids, list)
                and primary_item_id in item_ids
                and child_item_id in item_ids
            ):
                matches.append(quota)
        if len(matches) != 1 or not isinstance(matches[0].get("id"), int):
            raise PretixUnavailable("Pretix template capacity mapping is incomplete or ambiguous")
        return matches[0]
