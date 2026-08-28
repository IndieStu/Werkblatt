from uuid import UUID

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from werkblatt.workshops.models import Workshop

from .forms import DocumentationForm, FacilitatorFormSet, ParticipantFormSet
from .models import Documentation, ParticipantEntry
from .services import (
    ConcurrentDocumentationUpdate,
    FacilitatorInput,
    ParticipantInput,
    get_or_create_documentation,
    reopen_documentation,
    save_and_finalize,
    save_draft,
    statistics_for,
)


def _workshop_for_request(request: HttpRequest, workshop_id: UUID) -> Workshop:
    try:
        return Workshop.objects.for_organization(request.organization_context.organization_id).get(
            pk=workshop_id
        )
    except Workshop.DoesNotExist as exc:
        raise Http404 from exc


def _participant_inputs(formset) -> list[ParticipantInput]:
    rows = []
    for form in formset.forms:
        if not form.cleaned_data:
            continue
        rows.append(
            ParticipantInput(
                entry_id=form.instance.pk if form.instance._state.adding is False else None,
                display_name=form.cleaned_data.get("display_name", ""),
                present=form.cleaned_data.get("present", False),
                delete=form.cleaned_data.get("DELETE", False),
            )
        )
    return rows


def _facilitator_inputs(formset) -> list[FacilitatorInput]:
    rows = []
    for form in formset.forms:
        if not form.cleaned_data:
            continue
        rows.append(
            FacilitatorInput(
                facilitator_id=form.instance.pk if form.instance._state.adding is False else None,
                display_name=form.cleaned_data.get("display_name", ""),
                delete=form.cleaned_data.get("DELETE", False),
            )
        )
    return rows


@login_required
def documentation_detail(request: HttpRequest, workshop_id: UUID) -> HttpResponse:
    workshop = _workshop_for_request(request, workshop_id)
    documentation = get_or_create_documentation(workshop=workshop, user=request.user)

    if request.method == "POST" and request.POST.get("action") == "reopen":
        try:
            reopen_documentation(
                documentation_id=documentation.id,
                organization_id=request.organization_context.organization_id,
                user=request.user,
                expected_version=int(request.POST.get("expected_version", "0")),
            )
            messages.success(request, "Dokumentation zur Korrektur geöffnet.")
        except (ValueError, ValidationError) as exc:
            messages.error(
                request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)
            )
        return redirect("documentation-detail", workshop_id=workshop.id)

    if documentation.status == Documentation.Status.FINALIZED:
        latest = documentation.revisions.first()
        return render(
            request,
            "documentation/detail.html",
            {
                "workshop": workshop,
                "documentation": documentation,
                "latest_revision": latest,
                "statistics": latest.snapshot.get("statistics", {}) if latest else {},
                "revisions": documentation.revisions.all(),
            },
        )

    form = DocumentationForm(request.POST or None, instance=documentation)
    participant_formset = ParticipantFormSet(
        request.POST or None,
        instance=documentation,
        prefix="participants",
        queryset=documentation.participants.all(),
    )
    facilitator_formset = FacilitatorFormSet(
        request.POST or None,
        instance=documentation,
        prefix="facilitators",
        queryset=documentation.facilitators.all(),
    )

    if request.method == "POST" and request.POST.get("action") in {"save", "finalize"}:
        if form.is_valid() and participant_formset.is_valid() and facilitator_formset.is_valid():
            values = {
                "documentation_id": documentation.id,
                "organization_id": request.organization_context.organization_id,
                "user": request.user,
                "expected_version": form.cleaned_data["expected_version"],
                "conducted_as_planned": form.cleaned_data["conducted_as_planned"],
                "report": form.cleaned_data["report"],
                "participants": _participant_inputs(participant_formset),
                "facilitators": _facilitator_inputs(facilitator_formset),
            }
            try:
                if request.POST["action"] == "finalize":
                    save_and_finalize(**values)
                    messages.success(request, "Dokumentation abgeschlossen.")
                else:
                    save_draft(**values)
                    messages.success(request, "Entwurf gespeichert.")
                return redirect("documentation-detail", workshop_id=workshop.id)
            except ConcurrentDocumentationUpdate as exc:
                form.add_error(None, exc)
            except (PermissionDenied, ValidationError) as exc:
                form.add_error(None, exc)

    return render(
        request,
        "documentation/detail.html",
        {
            "workshop": workshop,
            "documentation": documentation,
            "form": form,
            "participant_formset": participant_formset,
            "facilitator_formset": facilitator_formset,
            "statistics": statistics_for(documentation),
            "registered_origin": ParticipantEntry.Origin.REGISTERED,
            "revisions": documentation.revisions.all(),
        },
    )
