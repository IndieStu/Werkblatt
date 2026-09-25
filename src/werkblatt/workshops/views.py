import calendar
from datetime import date, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
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
    PretixEventCreationPresetForm,
    PretixEventRuleForm,
    PretixFundingTextForm,
    PretixWorkshopCreationForm,
    WorkshopFilterForm,
    WorkshopRequirementForm,
)
from .models import (
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
    month = _calendar_month(request.GET.get("month"))
    form = WorkshopFilterForm(request.GET or {"visibility": Workshop.Visibility.ACTIVE})
    month_calendar = calendar.Calendar(firstweekday=0)
    calendar_dates = month_calendar.monthdatescalendar(month.year, month.month)
    first_day = calendar_dates[0][0]
    last_day = calendar_dates[-1][-1]
    workshops = (
        Workshop.objects.for_organization(_organization_id(request))
        .select_related("documentation")
        .filter(starts_at__date__range=(first_day, last_day))
    )
    if form.is_valid():
        workshops = _filter_calendar_workshops(workshops, form.cleaned_data)
    else:
        workshops = workshops.filter(visibility=Workshop.Visibility.ACTIVE)
    workshops_by_day = {}
    for workshop in workshops.order_by("starts_at", "title"):
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
    defaults = {
        "visibility": Workshop.Visibility.ACTIVE,
        "date_from": timezone.localdate() - timedelta(days=30),
    }
    form = WorkshopFilterForm(request.GET or defaults)
    workshops = Workshop.objects.for_organization(_organization_id(request)).select_related(
        "documentation"
    )
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
    else:
        workshops = workshops.filter(
            visibility=Workshop.Visibility.ACTIVE,
            starts_at__date__gte=defaults["date_from"],
        )
    page = Paginator(workshops, 25).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    return render(
        request,
        "workshops/list.html",
        {
            "filter_form": form,
            "page": page,
            "query_without_page": query.urlencode(),
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
        if key not in {"q", "state", "visibility"}:
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
    form = PretixWorkshopCreationForm(
        request.POST or None,
        organization_id=_organization_id(request),
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
