from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from werkblatt.identities.policies import Capability, has_capability, require_capability

from .forms import PretixEventRuleForm, WorkshopFilterForm, WorkshopRequirementForm
from .models import PretixEventRule, Workshop
from .services import save_pretix_event_rule, set_documentation_requirement, set_workshop_visibility


def _organization_id(request):
    return request.organization_context.organization_id


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
            "can_manage_visibility": has_capability(
                request.user, _organization_id(request), Capability.MANAGE_WORKSHOP_VISIBILITY
            ),
            "can_manage_requirements": has_capability(
                request.user, _organization_id(request), Capability.MANAGE_INTEGRATIONS
            ),
        },
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
