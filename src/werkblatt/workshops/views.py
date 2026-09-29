import calendar
import csv
from datetime import date
from urllib.parse import quote, urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import HttpRequest, HttpResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from werkblatt.identities.models import User
from werkblatt.identities.policies import Capability, has_capability, require_capability
from werkblatt.integrations.pretix.client import (
    PretixClient,
    PretixConfigurationError,
    PretixUnavailable,
)
from werkblatt.integrations.pretix.creation import (
    PretixCreationPreset,
    PretixEventCreator,
    PretixEventDraft,
)

from .forms import (
    NativeWorkshopForm,
    OpenWorkshopAttendanceForm,
    OpenWorkshopSeriesForm,
    OpenWorkshopStatisticsFilterForm,
    PretixEventCreationPresetForm,
    PretixEventRuleForm,
    PretixFundingTextForm,
    PretixWorkshopCreationForm,
    WorkshopFilterForm,
    WorkshopRequirementForm,
)
from .models import (
    OpenWorkshopAttendance,
    OpenWorkshopSeries,
    PretixEventCreation,
    PretixEventCreationPreset,
    PretixEventRule,
    PretixFundingText,
    Workshop,
)
from .services import (
    claim_pretix_event_creation,
    complete_pretix_event_creation,
    fail_pretix_event_creation,
    materialize_pretix_event_creation,
    reserve_pretix_event_creation,
    save_native_workshop,
    save_pretix_creation_preset,
    save_pretix_event_rule,
    save_pretix_funding_text,
    set_documentation_requirement,
    set_workshop_visibility,
)


def _organization_id(request):
    return request.organization_context.organization_id


WORKSHOP_SCOPE_DOCUMENTATION = "documentation"
WORKSHOP_SCOPE_UPCOMING = "upcoming"


def _pretix_control_orders_url(workshop: Workshop) -> str:
    if workshop.source_type != Workshop.SourceType.PRETIX:
        return ""
    event_slug = workshop.parent_external_reference or workshop.external_reference.partition(":")[0]
    if not event_slug or not settings.PRETIX_ORGANIZER:
        return ""
    base = settings.PRETIX_BASE_URL.rstrip("/")
    organizer = quote(settings.PRETIX_ORGANIZER, safe="")
    event = quote(event_slug, safe="")
    url = f"{base}/control/event/{organizer}/{event}/orders/"
    prefix = f"{event_slug}:"
    if workshop.external_reference.startswith(prefix):
        subevent_id = workshop.external_reference[len(prefix) :]
        if subevent_id.isdigit():
            url = f"{url}?{urlencode({'subevent': subevent_id})}"
    return url


def _workshop_scope(request: HttpRequest) -> str:
    if request.GET.get("scope") == WORKSHOP_SCOPE_UPCOMING:
        return WORKSHOP_SCOPE_UPCOMING
    return WORKSHOP_SCOPE_DOCUMENTATION


def _apply_workshop_scope(workshops, scope: str):
    today = timezone.localdate()
    if scope == WORKSHOP_SCOPE_UPCOMING:
        return workshops.filter(starts_at__date__gt=today)
    return workshops.filter(starts_at__date__lte=today)


@login_required
def workshop_index(request: HttpRequest) -> HttpResponse:
    if request.user.preferred_workshop_view == User.WorkshopView.LIST:
        return redirect("workshop-list")
    return redirect("workshop-calendar")


@require_POST
@login_required
def workshop_view_preference(request: HttpRequest) -> HttpResponse:
    selected_view = request.POST.get("view")
    if selected_view not in User.WorkshopView.values:
        raise PermissionDenied("Ungültige Workshopansicht")
    if request.user.preferred_workshop_view != selected_view:
        request.user.preferred_workshop_view = selected_view
        request.user.save(update_fields=["preferred_workshop_view"])
    target = "workshop-calendar" if selected_view == User.WorkshopView.CALENDAR else "workshop-list"
    query = _view_switch_query(QueryDict(request.POST.get("query", "")))
    return redirect(f"{reverse(target)}?{query}" if query else target)


def _calendar_month(value: str | None) -> date:
    if value:
        try:
            parsed = date.fromisoformat(f"{value}-01")
            if 2000 <= parsed.year <= 2100:
                return parsed
        except ValueError:
            pass
    today = timezone.localdate()
    return today.replace(day=1)


def _shift_month(month: date, offset: int) -> date:
    year = month.year + (month.month - 1 + offset) // 12
    number = (month.month - 1 + offset) % 12 + 1
    return date(year, number, 1)


def _filter_calendar_workshops(workshops, data):
    visibility = data["visibility"] or Workshop.Visibility.ACTIVE
    if visibility != "all":
        workshops = workshops.filter(visibility=visibility)
    if data["q"]:
        workshops = workshops.filter(
            Q(title__icontains=data["q"]) | Q(location__icontains=data["q"])
        )
    state = data["state"]
    if state == "upcoming":
        workshops = workshops.filter(starts_at__gte=timezone.now())
    elif state == "undocumented":
        workshops = workshops.filter(
            lifecycle_status=Workshop.LifecycleStatus.ACTIVE,
            documentation__isnull=True,
            documentation_requirement=Workshop.DocumentationRequirement.REQUIRED,
        )
    elif state == "draft":
        workshops = workshops.filter(documentation__status="draft")
    elif state == "finalized":
        workshops = workshops.filter(documentation__status="finalized")
    elif state == "not_required":
        workshops = workshops.filter(
            documentation_requirement=Workshop.DocumentationRequirement.NOT_REQUIRED
        )
    elif state == "cancelled":
        workshops = workshops.filter(lifecycle_status=Workshop.LifecycleStatus.CANCELLED)
    return workshops


@login_required
def workshop_calendar(request: HttpRequest) -> HttpResponse:
    scope = _workshop_scope(request)
    month = _calendar_month(request.GET.get("month"))
    form_data = request.GET.copy()
    if "visibility" not in form_data:
        form_data["visibility"] = Workshop.Visibility.ACTIVE
    form = WorkshopFilterForm(form_data)
    month_calendar = calendar.Calendar(firstweekday=0)
    calendar_dates = month_calendar.monthdatescalendar(month.year, month.month)
    first_day = calendar_dates[0][0]
    last_day = calendar_dates[-1][-1]
    workshops = (
        Workshop.objects.for_organization(_organization_id(request))
        .select_related("documentation")
        .annotate(
            active_registration_count=Count(
                "registrations", filter=Q(registrations__active=True), distinct=True
            )
        )
        .filter(starts_at__date__range=(first_day, last_day))
    )
    workshops = _apply_workshop_scope(workshops, scope)
    if form.is_valid():
        workshops = _filter_calendar_workshops(workshops, form.cleaned_data)
        if scope == WORKSHOP_SCOPE_UPCOMING and not form.cleaned_data["state"]:
            workshops = workshops.filter(lifecycle_status=Workshop.LifecycleStatus.ACTIVE)
    else:
        workshops = workshops.filter(visibility=Workshop.Visibility.ACTIVE)
    workshops_by_day = {}
    for workshop in workshops.order_by("starts_at", "title"):
        workshop.pretix_control_orders_url = _pretix_control_orders_url(workshop)
        local_day = timezone.localtime(workshop.starts_at).date()
        workshops_by_day.setdefault(local_day, []).append(workshop)
    weeks = [
        [
            {
                "date": day,
                "in_month": day.month == month.month,
                "is_today": day == timezone.localdate(),
                "workshops": workshops_by_day.get(day, []),
            }
            for day in week
        ]
        for week in calendar_dates
    ]
    return render(
        request,
        "workshops/calendar.html",
        {
            "filter_form": form,
            "month": month,
            "previous_month": _shift_month(month, -1),
            "next_month": _shift_month(month, 1),
            "weeks": weeks,
            "scope": scope,
            "view_switch_query": _view_switch_query(request.GET),
            "can_create_pretix_workshops": has_capability(
                request.user,
                _organization_id(request),
                Capability.CREATE_AND_PUBLISH_PRETIX_EVENTS,
            ),
        },
    )


@login_required
def workshop_list(request: HttpRequest) -> HttpResponse:
    scope = _workshop_scope(request)
    form_data = request.GET.copy()
    if "visibility" not in form_data:
        form_data["visibility"] = Workshop.Visibility.ACTIVE
    form = WorkshopFilterForm(form_data)
    workshops = (
        Workshop.objects.for_organization(_organization_id(request))
        .select_related("documentation")
        .annotate(
            active_registration_count=Count(
                "registrations", filter=Q(registrations__active=True), distinct=True
            )
        )
    )
    workshops = _apply_workshop_scope(workshops, scope)
    if form.is_valid():
        data = form.cleaned_data
        if data["visibility"] != "all":
            workshops = workshops.filter(visibility=data["visibility"])
        if data["date_from"]:
            workshops = workshops.filter(starts_at__date__gte=data["date_from"])
        if data["date_to"]:
            workshops = workshops.filter(starts_at__date__lte=data["date_to"])
        if data["q"]:
            workshops = workshops.filter(
                Q(title__icontains=data["q"]) | Q(location__icontains=data["q"])
            )
        state = data["state"]
        if state == "upcoming":
            workshops = workshops.filter(starts_at__gte=timezone.now())
        elif state == "undocumented":
            workshops = workshops.filter(
                documentation__isnull=True,
                documentation_requirement=Workshop.DocumentationRequirement.REQUIRED,
            )
        elif state == "draft":
            workshops = workshops.filter(documentation__status="draft")
        elif state == "finalized":
            workshops = workshops.filter(documentation__status="finalized")
        elif state == "not_required":
            workshops = workshops.filter(
                documentation_requirement=Workshop.DocumentationRequirement.NOT_REQUIRED
            )
        elif state == "cancelled":
            workshops = workshops.filter(lifecycle_status=Workshop.LifecycleStatus.CANCELLED)
        if scope == WORKSHOP_SCOPE_UPCOMING and not state:
            workshops = workshops.filter(lifecycle_status=Workshop.LifecycleStatus.ACTIVE)
    else:
        workshops = workshops.filter(
            visibility=Workshop.Visibility.ACTIVE,
        )
        if scope == WORKSHOP_SCOPE_UPCOMING:
            workshops = workshops.filter(lifecycle_status=Workshop.LifecycleStatus.ACTIVE)
    if scope == WORKSHOP_SCOPE_UPCOMING:
        workshops = workshops.order_by("starts_at", "title")
    else:
        workshops = workshops.order_by("-starts_at", "title")
    page = Paginator(workshops, 25).get_page(request.GET.get("page"))
    for workshop in page.object_list:
        workshop.pretix_control_orders_url = _pretix_control_orders_url(workshop)
    query = request.GET.copy()
    query.pop("page", None)
    return render(
        request,
        "workshops/list.html",
        {
            "filter_form": form,
            "page": page,
            "query_without_page": query.urlencode(),
            "scope": scope,
            "view_switch_query": _view_switch_query(request.GET),
            "can_manage_visibility": has_capability(
                request.user, _organization_id(request), Capability.MANAGE_WORKSHOP_VISIBILITY
            ),
            "can_manage_requirements": has_capability(
                request.user, _organization_id(request), Capability.MANAGE_INTEGRATIONS
            ),
            "can_edit_native_workshops": has_capability(
                request.user, _organization_id(request), Capability.DOCUMENT_WORKSHOPS
            ),
            "can_create_pretix_workshops": has_capability(
                request.user,
                _organization_id(request),
                Capability.CREATE_AND_PUBLISH_PRETIX_EVENTS,
            ),
        },
    )


def _view_switch_query(source: QueryDict) -> str:
    query = source.copy()
    for key in list(query):
        if key not in {"q", "state", "visibility", "scope"}:
            query.pop(key, None)
    return query.urlencode()


@login_required
def native_workshop_edit(request: HttpRequest, workshop_id=None) -> HttpResponse:
    require_capability(
        request.user,
        _organization_id(request),
        Capability.DOCUMENT_WORKSHOPS,
        "Keine Berechtigung zum Anlegen oder Bearbeiten von Workshops.",
    )
    workshop = None
    if workshop_id is not None:
        workshop = get_object_or_404(
            Workshop.objects.for_organization(_organization_id(request)),
            pk=workshop_id,
            source_type=Workshop.SourceType.NATIVE,
        )
    form = NativeWorkshopForm(request.POST or None, instance=workshop)
    if request.method == "POST" and form.is_valid():
        workshop = save_native_workshop(
            form=form,
            organization=request.organization,
            user=request.user,
            workshop=workshop,
        )
        messages.success(
            request,
            "Workshop gespeichert."
            if workshop_id is not None
            else "Workshop angelegt. Die Dokumentation kann jetzt bearbeitet werden.",
        )
        return redirect("documentation-detail", workshop_id=workshop.id)
    return render(
        request,
        "workshops/form.html",
        {"form": form, "workshop": workshop},
    )


@login_required
def workshop_visibility(request: HttpRequest, workshop_id) -> HttpResponse:
    if request.method != "POST":
        raise PermissionDenied
    workshop = get_object_or_404(
        Workshop.objects.for_organization(_organization_id(request)), pk=workshop_id
    )
    try:
        set_workshop_visibility(
            workshop=workshop,
            organization=request.organization,
            user=request.user,
            visibility=request.POST.get("visibility", ""),
        )
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Workshop-Sichtbarkeit gespeichert.")
    return redirect("workshop-list")


@login_required
def workshop_requirement(request: HttpRequest, workshop_id) -> HttpResponse:
    require_capability(
        request.user,
        _organization_id(request),
        Capability.MANAGE_INTEGRATIONS,
        "Nur Organization Admins dürfen die Dokumentationspflicht ändern.",
    )
    workshop = get_object_or_404(
        Workshop.objects.for_organization(_organization_id(request)), pk=workshop_id
    )
    form = WorkshopRequirementForm(
        request.POST or None,
        initial={
            "documentation_requirement": workshop.documentation_requirement,
            "reason": workshop.requirement_reason,
        },
    )
    if request.method == "POST" and form.is_valid():
        set_documentation_requirement(
            workshop=workshop,
            organization=request.organization,
            user=request.user,
            requirement=form.cleaned_data["documentation_requirement"],
            reason=form.cleaned_data["reason"],
        )
        messages.success(request, "Dokumentationspflicht gespeichert.")
        return redirect("workshop-list")
    return render(
        request,
        "workshops/requirement.html",
        {"workshop": workshop, "form": form},
    )


@login_required
def pretix_rule_list(request: HttpRequest) -> HttpResponse:
    require_capability(
        request.user,
        _organization_id(request),
        Capability.MANAGE_INTEGRATIONS,
        "Nur Organization Admins dürfen Pretix-Regeln verwalten.",
    )
    rules = PretixEventRule.objects.filter(organization_id=_organization_id(request))
    return render(request, "workshops/pretix_rules/list.html", {"rules": rules})


@login_required
def pretix_rule_edit(request: HttpRequest, rule_id=None) -> HttpResponse:
    require_capability(
        request.user,
        _organization_id(request),
        Capability.MANAGE_INTEGRATIONS,
        "Nur Organization Admins dürfen Pretix-Regeln verwalten.",
    )
    rule = None
    if rule_id:
        rule = get_object_or_404(
            PretixEventRule.objects.filter(organization_id=_organization_id(request)), pk=rule_id
        )
    form = PretixEventRuleForm(
        request.POST or None, instance=rule, organization_id=_organization_id(request)
    )
    if request.method == "POST" and form.is_valid():
        save_pretix_event_rule(form=form, organization=request.organization, user=request.user)
        messages.success(request, "Pretix-Veranstaltungsregel gespeichert.")
        return redirect("pretix-rule-list")
    return render(request, "workshops/pretix_rules/form.html", {"form": form, "rule": rule})


@login_required
def pretix_creation_settings(request: HttpRequest) -> HttpResponse:
    require_capability(
        request.user,
        _organization_id(request),
        Capability.MANAGE_INTEGRATIONS,
        "Nur Organization Admins dürfen Pretix-Erstellungsstandards verwalten.",
    )
    return render(
        request,
        "workshops/pretix_creation/settings.html",
        {
            "presets": PretixEventCreationPreset.objects.filter(
                organization_id=_organization_id(request)
            ),
            "funding_texts": PretixFundingText.objects.filter(
                organization_id=_organization_id(request)
            ),
            "pretix_control_url": f"{settings.PRETIX_BASE_URL.rstrip('/')}/control",
        },
    )


@login_required
def pretix_creation_preset_edit(request: HttpRequest, preset_id=None) -> HttpResponse:
    require_capability(
        request.user,
        _organization_id(request),
        Capability.MANAGE_INTEGRATIONS,
        "Nur Organization Admins dürfen Pretix-Erstellungsstandards verwalten.",
    )
    preset = None
    if preset_id:
        preset = get_object_or_404(
            PretixEventCreationPreset.objects.filter(organization_id=_organization_id(request)),
            pk=preset_id,
        )
    form = PretixEventCreationPresetForm(
        request.POST or None,
        instance=preset,
        organization_id=_organization_id(request),
    )
    if request.method == "POST" and form.is_valid():
        save_pretix_creation_preset(
            form=form,
            organization=request.organization,
            user=request.user,
        )
        messages.success(request, "Pretix-Erstellungsstandard gespeichert.")
        return redirect("pretix-creation-settings")
    return render(
        request,
        "workshops/pretix_creation/preset_form.html",
        {"form": form, "preset": preset},
    )


@login_required
def pretix_funding_text_edit(request: HttpRequest, funding_text_id=None) -> HttpResponse:
    require_capability(
        request.user,
        _organization_id(request),
        Capability.MANAGE_INTEGRATIONS,
        "Nur Organization Admins dürfen Pretix-Fördertexte verwalten.",
    )
    funding_text = None
    if funding_text_id:
        funding_text = get_object_or_404(
            PretixFundingText.objects.filter(organization_id=_organization_id(request)),
            pk=funding_text_id,
        )
    form = PretixFundingTextForm(
        request.POST or None,
        instance=funding_text,
        organization_id=_organization_id(request),
    )
    if request.method == "POST" and form.is_valid():
        save_pretix_funding_text(
            form=form,
            organization=request.organization,
            user=request.user,
        )
        messages.success(request, "Pretix-Fördertext gespeichert.")
        return redirect("pretix-creation-settings")
    return render(
        request,
        "workshops/pretix_creation/funding_text_form.html",
        {"form": form, "funding_text": funding_text},
    )


@require_POST
@login_required
def pretix_creation_preset_check(request: HttpRequest, preset_id) -> HttpResponse:
    require_capability(
        request.user,
        _organization_id(request),
        Capability.MANAGE_INTEGRATIONS,
        "Nur Organization Admins dürfen Pretix-Erstellungsstandards prüfen.",
    )
    preset = get_object_or_404(
        PretixEventCreationPreset.objects.filter(organization_id=_organization_id(request)),
        pk=preset_id,
    )
    client = None
    try:
        client = PretixClient(settings.PRETIX_BASE_URL, settings.PRETIX_API_TOKEN)
        inspection = PretixEventCreator(client, settings.PRETIX_ORGANIZER).inspect_template(
            PretixCreationPreset(
                template_event_slug=preset.template_event_slug,
                primary_item_internal_name=preset.primary_item_internal_name,
                child_item_internal_name=preset.child_item_internal_name,
            )
        )
    except (PretixConfigurationError, PretixUnavailable, ValueError):
        messages.error(
            request,
            "Die Pretix-Vorlage konnte nicht sicher bestätigt werden. "
            "Bitte Konfiguration und Vorlage prüfen.",
        )
    else:
        capacity = "unbegrenzt" if inspection.capacity is None else str(inspection.capacity)
        messages.success(
            request,
            f"Vorlage bestätigt: Standard- und Kinderticket, gemeinsame Kapazität {capacity}.",
        )
    finally:
        if client is not None:
            client.close()
    return redirect("pretix-creation-settings")


@login_required
def pretix_workshop_create(request: HttpRequest) -> HttpResponse:
    require_capability(
        request.user,
        _organization_id(request),
        Capability.CREATE_AND_PUBLISH_PRETIX_EVENTS,
        "Keine Berechtigung zum Erstellen von Pretix-Workshops.",
    )
    location_choices = (
        Workshop.objects.for_organization(_organization_id(request))
        .exclude(location="")
        .order_by("location")
        .values_list("location", flat=True)
        .distinct()
    )
    form = PretixWorkshopCreationForm(
        request.POST or None,
        organization_id=_organization_id(request),
        location_choices=location_choices,
    )
    if request.method == "POST" and form.is_valid():
        client = None
        try:
            client = PretixClient(settings.PRETIX_BASE_URL, settings.PRETIX_API_TOKEN)
            external_slugs = PretixEventCreator(
                client, settings.PRETIX_ORGANIZER
            ).list_event_slugs()
        except (PretixConfigurationError, PretixUnavailable, ValueError):
            form.add_error(
                None,
                "Pretix konnte nicht sicher geprüft werden. Bitte später erneut versuchen.",
            )
        else:
            creation = reserve_pretix_event_creation(
                organization=request.organization,
                user=request.user,
                preset=form.cleaned_data["preset"],
                funding_text=form.cleaned_data["funding_text"],
                title=form.cleaned_data["title"],
                description=form.cleaned_data["description"],
                starts_at=form.cleaned_data["starts_at"],
                ends_at=form.cleaned_data["ends_at"],
                registration_deadline=form.cleaned_data["registration_deadline"],
                location=form.cleaned_data["location"],
                capacity=form.cleaned_data["capacity"],
                child_registration_enabled=form.cleaned_data["child_registration_enabled"],
                existing_external_slugs=external_slugs,
            )
            return redirect("pretix-workshop-review", creation_id=creation.id)
        finally:
            if client is not None:
                client.close()
    return render(
        request,
        "workshops/pretix_creation/workshop_form.html",
        {
            "form": form,
            "pretix_control_url": f"{settings.PRETIX_BASE_URL.rstrip('/')}/control",
        },
    )


@login_required
def pretix_workshop_review(request: HttpRequest, creation_id) -> HttpResponse:
    require_capability(
        request.user,
        _organization_id(request),
        Capability.CREATE_AND_PUBLISH_PRETIX_EVENTS,
        "Keine Berechtigung zum Erstellen von Pretix-Workshops.",
    )
    creation = get_object_or_404(
        PretixEventCreation.objects.filter(
            organization_id=_organization_id(request),
            created_by=request.user,
        ).select_related("preset", "funding_text"),
        pk=creation_id,
    )
    return render(
        request,
        "workshops/pretix_creation/workshop_review.html",
        {
            "creation": creation,
            "pretix_control_url": f"{settings.PRETIX_BASE_URL.rstrip('/')}/control",
        },
    )


@require_POST
@login_required
def pretix_workshop_publish(request: HttpRequest, creation_id) -> HttpResponse:
    require_capability(
        request.user,
        _organization_id(request),
        Capability.CREATE_AND_PUBLISH_PRETIX_EVENTS,
        "Keine Berechtigung zum Erstellen von Pretix-Workshops.",
    )
    creation = get_object_or_404(
        PretixEventCreation.objects.filter(
            organization_id=_organization_id(request),
            created_by=request.user,
        ),
        pk=creation_id,
    )
    try:
        creation = claim_pretix_event_creation(
            creation_id=creation.id,
            organization=request.organization,
            user=request.user,
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("pretix-workshop-review", creation_id=creation.id)

    client = None
    failure_code = PretixEventCreation.FailureCode.PRETIX_UNAVAILABLE
    try:
        client = PretixClient(settings.PRETIX_BASE_URL, settings.PRETIX_API_TOKEN)
        creator = PretixEventCreator(client, settings.PRETIX_ORGANIZER)
        snapshot = creation.preset_snapshot
        creator.create_from_template(
            draft=PretixEventDraft(
                slug=creation.external_slug,
                title=creation.title,
                starts_at=creation.starts_at,
                ends_at=creation.ends_at,
                registration_deadline=creation.registration_deadline,
                location=creation.location,
                capacity=creation.capacity,
                child_registration_enabled=creation.child_registration_enabled,
                description=creation.description,
                funding_text=creation.funding_text_snapshot,
            ),
            preset=PretixCreationPreset(
                template_event_slug=snapshot["template_event_slug"],
                primary_item_internal_name=snapshot["primary_item_internal_name"],
                child_item_internal_name=snapshot["child_item_internal_name"],
            ),
        )
        published = creator.publish_event(creation.external_slug)
    except (KeyError, PretixConfigurationError, ValueError):
        failure_code = PretixEventCreation.FailureCode.TEMPLATE_INVALID
        published = None
    except PretixUnavailable:
        published = None
    finally:
        if client is not None:
            client.close()

    if published is None:
        fail_pretix_event_creation(
            creation_id=creation.id,
            organization=request.organization,
            failure_code=failure_code,
        )
        messages.error(
            request,
            "Die Pretix-Veranstaltung konnte nicht vollständig erstellt und bestätigt werden. "
            "Es wurde keine automatische Wiederholung ausgeführt.",
        )
        return redirect("pretix-workshop-review", creation_id=creation.id)

    complete_pretix_event_creation(
        creation_id=creation.id,
        organization=request.organization,
        external_url=published.public_url,
    )
    workshop = materialize_pretix_event_creation(
        creation_id=creation.id,
        organization=request.organization,
    )
    messages.success(request, "Workshop in Pretix erstellt und veröffentlicht.")
    return redirect("documentation-detail", workshop_id=workshop.id)


def _open_workshop_attendances(request: HttpRequest, form):
    attendances = OpenWorkshopAttendance.objects.filter(
        organization_id=_organization_id(request)
    ).select_related("series")
    if form.is_valid():
        if form.cleaned_data["date_from"]:
            attendances = attendances.filter(occurred_on__gte=form.cleaned_data["date_from"])
        if form.cleaned_data["date_to"]:
            attendances = attendances.filter(occurred_on__lte=form.cleaned_data["date_to"])
        if form.cleaned_data["series"]:
            attendances = attendances.filter(series=form.cleaned_data["series"])
    return attendances


def _csv_cell(value) -> str:
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{text}"
    return text


@login_required
def open_workshop_dashboard(request: HttpRequest) -> HttpResponse:
    require_capability(
        request.user,
        _organization_id(request),
        Capability.RECORD_OPEN_WORKSHOP_ATTENDANCE,
        "Keine Berechtigung für offene Werkstätten.",
    )
    filter_form = OpenWorkshopStatisticsFilterForm(
        request.GET,
        organization_id=_organization_id(request),
    )
    attendances = _open_workshop_attendances(request, filter_form)
    totals = attendances.aggregate(
        visits=Count("id"),
        total=Sum("total"),
        female=Sum("female"),
        male=Sum("male"),
        diverse=Sum("diverse"),
        unspecified=Sum("unspecified"),
    )
    visits = totals["visits"] or 0
    totals["average"] = round((totals["total"] or 0) / visits, 1) if visits else 0
    by_series = (
        attendances.values("series__name")
        .annotate(visits=Count("id"), total=Sum("total"))
        .order_by("series__name")
    )
    return render(
        request,
        "workshops/open_workshops/dashboard.html",
        {
            "filter_form": filter_form,
            "totals": totals,
            "by_series": by_series,
            "recent_attendances": attendances.order_by("-occurred_on", "series__name")[:25],
            "can_manage_series": has_capability(
                request.user,
                _organization_id(request),
                Capability.MANAGE_OPEN_WORKSHOP_SERIES,
            ),
        },
    )


@login_required
def open_workshop_attendance_edit(request: HttpRequest, attendance_id=None) -> HttpResponse:
    require_capability(
        request.user,
        _organization_id(request),
        Capability.RECORD_OPEN_WORKSHOP_ATTENDANCE,
        "Keine Berechtigung zum Erfassen offener Werkstätten.",
    )
    attendance = None
    if attendance_id:
        attendance = get_object_or_404(
            OpenWorkshopAttendance.objects.filter(organization_id=_organization_id(request)),
            pk=attendance_id,
        )
    form = OpenWorkshopAttendanceForm(
        request.POST or None,
        instance=attendance,
        organization_id=_organization_id(request),
    )
    if request.method == "POST" and form.is_valid():
        saved = form.save(commit=False)
        saved.organization = request.organization
        if saved._state.adding:
            saved.recorded_by = request.user
        saved.full_clean()
        saved.save()
        messages.success(request, "Besuchszahlen gespeichert.")
        return redirect("open-workshop-dashboard")
    return render(
        request,
        "workshops/open_workshops/attendance_form.html",
        {"form": form, "attendance": attendance},
    )


@login_required
def open_workshop_series_list(request: HttpRequest) -> HttpResponse:
    require_capability(
        request.user,
        _organization_id(request),
        Capability.MANAGE_OPEN_WORKSHOP_SERIES,
        "Nur Editors und Organization Admins dürfen Reihen konfigurieren.",
    )
    series = OpenWorkshopSeries.objects.filter(organization_id=_organization_id(request))
    return render(
        request,
        "workshops/open_workshops/series_list.html",
        {"series_list": series},
    )


@login_required
def open_workshop_series_edit(request: HttpRequest, series_id=None) -> HttpResponse:
    require_capability(
        request.user,
        _organization_id(request),
        Capability.MANAGE_OPEN_WORKSHOP_SERIES,
        "Nur Editors und Organization Admins dürfen Reihen konfigurieren.",
    )
    series = None
    if series_id:
        series = get_object_or_404(
            OpenWorkshopSeries.objects.filter(organization_id=_organization_id(request)),
            pk=series_id,
        )
    form = OpenWorkshopSeriesForm(
        request.POST or None,
        instance=series,
        organization_id=_organization_id(request),
    )
    if request.method == "POST" and form.is_valid():
        saved = form.save(commit=False)
        saved.organization = request.organization
        saved.full_clean()
        saved.save()
        messages.success(request, "Reihe gespeichert.")
        return redirect("open-workshop-series-list")
    return render(
        request,
        "workshops/open_workshops/series_form.html",
        {"form": form, "series": series},
    )


@login_required
def open_workshop_statistics_csv(request: HttpRequest) -> HttpResponse:
    require_capability(
        request.user,
        _organization_id(request),
        Capability.RECORD_OPEN_WORKSHOP_ATTENDANCE,
        "Keine Berechtigung für offene Werkstätten.",
    )
    form = OpenWorkshopStatisticsFilterForm(
        request.GET,
        organization_id=_organization_id(request),
    )
    if not form.is_valid():
        return HttpResponse("Ungültiger Statistikzeitraum.", status=400)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="Werkblatt_Offene_Werkstaetten.csv"'
    response.write("\ufeff")
    writer = csv.writer(response, delimiter=";")
    writer.writerow(["Datum", "Reihe", "Gesamt", "Weiblich", "Männlich", "Divers", "Keine Angabe"])
    for attendance in _open_workshop_attendances(request, form).order_by(
        "occurred_on", "series__name"
    ):
        writer.writerow(
            [
                _csv_cell(value)
                for value in (
                    attendance.occurred_on.isoformat(),
                    attendance.series.name,
                    attendance.total,
                    attendance.female,
                    attendance.male,
                    attendance.diverse,
                    attendance.unspecified,
                )
            ]
        )
    return response
