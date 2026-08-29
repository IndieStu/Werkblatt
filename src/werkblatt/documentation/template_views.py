from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from werkblatt.identities.policies import Capability, require_capability

from .models import DocumentTemplate, TemplateOutputDefinition
from .template_forms import (
    AssetPlacementFormSet,
    CustomFieldDefinitionFormSet,
    OutputDefinitionFormSet,
    TemplateForm,
)
from .templates_service import duplicate_template, save_template, template_initial


def _require_template_management(request):
    require_capability(
        request.user,
        request.organization_context.organization_id,
        Capability.MANAGE_DOCUMENT_TEMPLATES,
        "Keine Berechtigung zur Verwaltung von Dokumentvorlagen.",
    )


def _forms(request, *, initial=None):
    bound = request.method == "POST"
    template_form = TemplateForm(
        request.POST if bound else None, initial=(initial or {}).get("template")
    )
    assets = AssetPlacementFormSet(
        request.POST if bound else None,
        prefix="assets",
        initial=(initial or {}).get("assets"),
        form_kwargs={"organization_id": request.organization_context.organization_id},
    )
    outputs = OutputDefinitionFormSet(
        request.POST if bound else None,
        prefix="outputs",
        initial=(initial or {}).get("outputs"),
    )
    fields = CustomFieldDefinitionFormSet(
        request.POST if bound else None,
        prefix="fields",
        initial=(initial or {}).get("fields"),
    )
    return template_form, assets, outputs, fields


@login_required
def template_list(request: HttpRequest) -> HttpResponse:
    _require_template_management(request)
    templates = DocumentTemplate.objects.for_organization(
        request.organization_context.organization_id
    ).select_related("current_version")
    return render(request, "documentation/templates/list.html", {"templates": templates})


@login_required
def template_create(request: HttpRequest) -> HttpResponse:
    _require_template_management(request)
    initial = {
        "template": {
            "status": DocumentTemplate.Status.ACTIVE,
            "attendance_text": (
                "Mit dem Eintrag auf dieser Liste bestätige ich die Teilnahme an oben "
                "aufgeführtem Workshop."
            ),
        },
        "outputs": [
            {
                "kind": TemplateOutputDefinition.Kind.FINAL_REPORT,
                "display_name": "Abschlussdokument",
                "enabled": True,
                "include_statistics": True,
                "include_report": True,
                "include_facilitators": True,
            },
            {
                "kind": TemplateOutputDefinition.Kind.ATTENDANCE_SHEET,
                "display_name": "Teilnahmeliste",
                "enabled": True,
                "include_participant_names": True,
                "include_signature_column": True,
                "include_statistics": False,
                "include_report": False,
                "include_facilitators": False,
            },
        ],
    }
    forms = _forms(request, initial=initial)
    if (
        request.method == "POST"
        and request.POST.get("action") == "save_template"
        and all(form.is_valid() for form in forms)
    ):
        try:
            template = save_template(
                organization=request.organization,
                user=request.user,
                template=None,
                template_data=forms[0].cleaned_data,
                assets=forms[1].cleaned_data,
                outputs=forms[2].cleaned_data,
                fields=forms[3].cleaned_data,
            )
        except ValidationError as exc:
            forms[0].add_error(None, exc)
        else:
            messages.success(request, "Dokumentvorlage erstellt.")
            return redirect("template-edit", template_id=template.id)
    return render(request, "documentation/templates/form.html", {"forms": forms})


@login_required
def template_edit(request: HttpRequest, template_id) -> HttpResponse:
    _require_template_management(request)
    template = get_object_or_404(
        DocumentTemplate.objects.for_organization(request.organization_context.organization_id),
        pk=template_id,
    )
    initial = template_initial(template)
    outdated_assets = [
        item
        for item in initial["assets"]
        if item["asset_version_id"] and item["asset"].current_version_id != item["asset_version_id"]
    ]
    forms = _forms(request, initial=initial)
    if (
        request.method == "POST"
        and request.POST.get("action") == "save_template"
        and all(form.is_valid() for form in forms)
    ):
        try:
            save_template(
                organization=request.organization,
                user=request.user,
                template=template,
                template_data=forms[0].cleaned_data,
                assets=forms[1].cleaned_data,
                outputs=forms[2].cleaned_data,
                fields=forms[3].cleaned_data,
            )
        except ValidationError as exc:
            forms[0].add_error(None, exc)
        else:
            messages.success(request, "Änderungen als neuer Vorlagenstand gespeichert.")
            return redirect("template-edit", template_id=template.id)
    return render(
        request,
        "documentation/templates/form.html",
        {"forms": forms, "template": template, "outdated_assets": outdated_assets},
    )


@login_required
def template_duplicate(request: HttpRequest, template_id) -> HttpResponse:
    _require_template_management(request)
    if request.method != "POST":
        raise PermissionDenied
    template = get_object_or_404(
        DocumentTemplate.objects.for_organization(request.organization_context.organization_id),
        pk=template_id,
    )
    duplicated = duplicate_template(
        template=template, organization=request.organization, user=request.user
    )
    messages.success(request, "Vorlage unabhängig dupliziert.")
    return redirect("template-edit", template_id=duplicated.id)
