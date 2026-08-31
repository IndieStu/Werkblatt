from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation

from django.db.models import OuterRef, Subquery
from django.utils import timezone

from werkblatt.workshops.models import Workshop

from .models import Documentation, DocumentationRevision


@dataclass(frozen=True)
class StatisticsPeriod:
    date_from: date
    date_to: date


def current_year_period() -> StatisticsPeriod:
    today = timezone.localdate()
    return StatisticsPeriod(date(today.year, 1, 1), today)


def _period_bounds(period: StatisticsPeriod) -> tuple[datetime, datetime]:
    current_timezone = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(period.date_from, time.min), current_timezone)
    end = timezone.make_aware(datetime.combine(period.date_to, time.max), current_timezone)
    return start, end


def _latest_revisions(organization_id, period: StatisticsPeriod):
    start, end = _period_bounds(period)
    latest_revision_id = (
        DocumentationRevision.objects.filter(documentation_id=OuterRef("documentation_id"))
        .order_by("-number")
        .values("id")[:1]
    )
    return list(
        DocumentationRevision.objects.filter(
            organization_id=organization_id,
            documentation__workshop__starts_at__range=(start, end),
            id=Subquery(latest_revision_id),
        )
        .select_related("documentation", "documentation__workshop")
        .order_by("documentation_id")
    )


def _number(value) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _decimal_display(value: Decimal) -> str:
    if value == value.to_integral():
        return str(int(value))
    return format(value.normalize(), "f").replace(".", ",")


def organization_statistics(*, organization_id, period: StatisticsPeriod) -> dict:
    start, end = _period_bounds(period)
    workshops = Workshop.objects.for_organization(organization_id).filter(
        starts_at__range=(start, end)
    )
    workshop_count = workshops.count()
    latest_revisions = _latest_revisions(organization_id, period)
    totals = defaultdict(int)
    custom_totals = defaultdict(Decimal)
    groups = {}
    correction_pending = 0

    for revision in latest_revisions:
        snapshot = revision.snapshot
        statistics = snapshot.get("statistics", {})
        for key in ["registered", "present_registered", "walk_ins", "present_total", "no_shows"]:
            totals[key] += int(statistics.get(key, 0) or 0)

        template = snapshot.get("template") or {}
        group_key = template.get("id") or "without-template"
        group = groups.setdefault(
            group_key,
            {
                "template_name": template.get("name") or "Ohne Dokumentvorlage",
                "project_title": template.get("project_title") or "Ohne Projekttitel",
                "workshops": 0,
                "registered": 0,
                "present_total": 0,
                "walk_ins": 0,
                "custom_statistics": defaultdict(Decimal),
            },
        )
        group["workshops"] += 1
        for key in ["registered", "present_total", "walk_ins"]:
            group[key] += int(statistics.get(key, 0) or 0)

        for field in template.get("custom_fields", []):
            if field.get("presentation") != "aggregate_statistic":
                continue
            value = _number(field.get("value"))
            if value is None:
                continue
            label = str(field.get("label") or "Zusatzangabe")
            custom_totals[label] += value
            group["custom_statistics"][label] += value

        if revision.documentation.status == Documentation.Status.DRAFT:
            correction_pending += 1

    registered = totals["registered"]
    attendance_rate = (
        Decimal(totals["present_registered"]) * Decimal(100) / Decimal(registered)
        if registered
        else None
    )
    group_rows = []
    for group in sorted(
        groups.values(), key=lambda item: (item["project_title"], item["template_name"])
    ):
        group_rows.append(
            {
                **group,
                "custom_statistics": [
                    {"label": label, "value": _decimal_display(value)}
                    for label, value in sorted(group["custom_statistics"].items())
                ],
            }
        )

    return {
        "period": period,
        "workshops": workshop_count,
        "finalized_workshops": len(latest_revisions),
        "without_finalization": workshop_count - len(latest_revisions),
        "correction_pending": correction_pending,
        "registered": registered,
        "present_registered": totals["present_registered"],
        "walk_ins": totals["walk_ins"],
        "present_total": totals["present_total"],
        "no_shows": totals["no_shows"],
        "attendance_rate": (
            _decimal_display(attendance_rate.quantize(Decimal("0.1")))
            if attendance_rate is not None
            else None
        ),
        "custom_statistics": [
            {"label": label, "value": _decimal_display(value)}
            for label, value in sorted(custom_totals.items())
        ],
        "groups": group_rows,
    }
