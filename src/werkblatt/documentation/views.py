from uuid import UUID

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from werkblatt.documents.rendering import render_revision_outputs
from werkblatt.documents.storage import store_via_webdav
from werkblatt.workshops.models import Workshop

from .forms import DocumentationForm, FacilitatorFormSet, ParticipantFormSet
from .models import Documentation, ParticipantEntry, WorkshopTemplateAssignment
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
from .template_forms import DocumentationCustomFieldsForm, WorkshopTemplateForm


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
    assignment_form = None

    if request.method == "POST" and request.POST.get("action") == "assign_template":
        if documentation.status != Documentation.Status.DRAFT:
            messages.error(request, "Vorlage kann nur im Entwurf gewechselt werden.")
            return redirect("documentation-detail", workshop_id=workshop.id)
        assignment_form = WorkshopTemplateForm(
            request.POST,
            organization_id=request.organization_context.organization_id,
        )
        if assignment_form.is_valid():
            template = assignment_form.cleaned_data["template"]
            assignment, _ = WorkshopTemplateAssignment.objects.update_or_create(
                organization_id=request.organization_context.organization_id,
                workshop=workshop,
                defaults={
                    "template": template,
                    "template_version": template.current_version,
                    "assigned_by": request.user,
                },
            )
            documentation.template_assignment = assignment
            documentation.updated_by = request.user
            documentation.version += 1
            documentation.save(
                update_fields=["template_assignment", "updated_by", "version", "updated_at"]
            )
            messages.success(request, "Dokumentvorlage zugeordnet.")
            return redirect("documentation-detail", workshop_id=workshop.id)
        else:
            messages.error(request, "Dokumentvorlage konnte nicht zugeordnet werden.")
            # Keep the bound form and its concrete validation error visible.

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
                "generated_documents": documentation.workshop.generated_documents.filter(
                    revision=latest
                ),
            },
        )

    is_documentation_post = request.method == "POST" and request.POST.get("action") in {
        "save",
        "finalize",
    }
    documentation_data = request.POST if is_documentation_post else None
    form = DocumentationForm(documentation_data, instance=documentation)
    if assignment_form is None:
        assignment_form = WorkshopTemplateForm(
            organization_id=request.organization_context.organization_id,
            initial={
                "template": (
                    documentation.template_assignment.template_id
                    if documentation.template_assignment_id
                    else None
                )
            },
        )
    definitions = (
        documentation.template_assignment.template_version.custom_fields.filter(active=True)
        if documentation.template_assignment_id
        else []
    )
    existing_custom_values = {
        str(value.field_stable_key): value.value
        for value in documentation.custom_field_values.all()
    }
    custom_form = DocumentationCustomFieldsForm(
        documentation_data,
        definitions=definitions,
        values=existing_custom_values,
    )
    participant_formset = ParticipantFormSet(
        documentation_data,
        instance=documentation,
        prefix="participants",
        queryset=documentation.participants.all(),
    )
    facilitator_formset = FacilitatorFormSet(
        documentation_data,
        instance=documentation,
        prefix="facilitators",
        queryset=documentation.facilitators.all(),
    )

    if is_documentation_post:
        if (
            form.is_valid()
            and participant_formset.is_valid()
            and facilitator_formset.is_valid()
            and custom_form.is_valid()
        ):
            values = {
                "documentation_id": documentation.id,
                "organization_id": request.organization_context.organization_id,
                "user": request.user,
                "expected_version": form.cleaned_data["expected_version"],
                "conducted_as_planned": form.cleaned_data["conducted_as_planned"],
                "report": form.cleaned_data["report"],
                "participants": _participant_inputs(participant_formset),
                "facilitators": _facilitator_inputs(facilitator_formset),
                "custom_values": custom_form.values_by_stable_key(),
            }
            try:
                if request.POST["action"] == "finalize":
                    revision = save_and_finalize(**values)
                    try:
                        for generated_document in render_revision_outputs(revision, request.user):
                            store_via_webdav(generated_document)
                    except Exception:
                        messages.warning(
                            request,
                            "Dokumentation abgeschlossen. Die PDF-Erzeugung ist fehlgeschlagen "
                            "und kann unabhängig wiederholt werden.",
                        )
                    else:
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
            "assignment_form": assignment_form,
            "custom_form": custom_form,
            "statistics": statistics_for(documentation),
            "registered_origin": ParticipantEntry.Origin.REGISTERED,
            "revisions": documentation.revisions.all(),
            "attendance_available": (
                documentation.template_assignment_id
                and documentation.template_assignment.template_version.outputs.filter(
                    kind="attendance_sheet", enabled=True
                ).exists()
            ),
        },
    )
