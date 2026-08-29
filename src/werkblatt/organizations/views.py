from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from werkblatt.identities.policies import (
    Capability,
    capabilities_for,
    has_capability,
    require_capability,
)

from .assets import add_asset_version, create_asset
from .forms import (
    BrandAssetEditForm,
    BrandAssetUploadForm,
    BrandAssetVersionForm,
    OrganizationProfileForm,
)
from .models import BrandAsset, BrandAssetVersion


def _organization_id(request: HttpRequest):
    return request.organization_context.organization_id


def _require(request: HttpRequest, capability: Capability, message: str) -> None:
    require_capability(request.user, _organization_id(request), capability, message)


def _can_manage_organization_branding(request: HttpRequest) -> bool:
    return has_capability(
        request.user,
        _organization_id(request),
        Capability.MANAGE_ORGANIZATION_BRANDING,
    )


@login_required
def settings_home(request: HttpRequest) -> HttpResponse:
    capabilities = capabilities_for(request.user, _organization_id(request))
    if not capabilities.intersection(
        {
            Capability.MANAGE_DOCUMENT_TEMPLATES,
            Capability.MANAGE_DOCUMENT_ASSETS,
            Capability.MANAGE_ORGANIZATION_PROFILE,
        }
    ):
        raise PermissionDenied("Keine Berechtigung für diesen Verwaltungsbereich.")
    return render(request, "organizations/settings_home.html", {"capabilities": capabilities})


@login_required
def organization_profile(request: HttpRequest) -> HttpResponse:
    _require(
        request,
        Capability.MANAGE_ORGANIZATION_PROFILE,
        "Nur Organization Admins dürfen das Organisationsprofil ändern.",
    )
    organization = request.organization
    form = OrganizationProfileForm(request.POST or None, instance=organization)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Organisationsprofil gespeichert.")
        return redirect("organization-profile")
    return render(request, "organizations/profile.html", {"form": form})


@login_required
def asset_list(request: HttpRequest) -> HttpResponse:
    _require(
        request,
        Capability.MANAGE_DOCUMENT_ASSETS,
        "Keine Berechtigung zur Verwaltung von Dokumentassets.",
    )
    assets = BrandAsset.objects.for_organization(
        request.organization_context.organization_id
    ).select_related("current_version")
    return render(
        request,
        "organizations/assets/list.html",
        {
            "assets": assets,
            "can_manage_organization_branding": _can_manage_organization_branding(request),
        },
    )


@login_required
def asset_create(request: HttpRequest) -> HttpResponse:
    _require(
        request,
        Capability.MANAGE_DOCUMENT_ASSETS,
        "Keine Berechtigung zum Hochladen von Dokumentassets.",
    )
    allow_organization_branding = _can_manage_organization_branding(request)
    form = BrandAssetUploadForm(
        request.POST or None,
        request.FILES or None,
        allow_organization_branding=allow_organization_branding,
    )
    if request.method == "POST" and form.is_valid():
        try:
            create_asset(
                organization=request.organization,
                user=request.user,
                display_name=form.cleaned_data["display_name"],
                default_role=form.cleaned_data["default_role"],
                upload=form.cleaned_data["file"],
            )
        except ValidationError as exc:
            form.add_error("file", exc)
        else:
            messages.success(request, "Logo sicher geprüft und gespeichert.")
            next_url = request.POST.get("next")
            if next_url and url_has_allowed_host_and_scheme(
                next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
            ):
                return redirect(next_url)
            return redirect("asset-list")
    return render(request, "organizations/assets/form.html", {"form": form})


@login_required
def asset_edit(request: HttpRequest, asset_id) -> HttpResponse:
    _require(
        request,
        Capability.MANAGE_DOCUMENT_ASSETS,
        "Keine Berechtigung zur Verwaltung von Dokumentassets.",
    )
    asset = get_object_or_404(
        BrandAsset.objects.for_organization(request.organization_context.organization_id),
        pk=asset_id,
    )
    allow_organization_branding = _can_manage_organization_branding(request)
    if asset.default_role == BrandAsset.Role.ORGANIZATION and not allow_organization_branding:
        raise PermissionDenied("Nur Organization Admins dürfen Organisationsassets verwalten.")
    form = BrandAssetEditForm(
        request.POST or None,
        instance=asset,
        allow_organization_branding=allow_organization_branding,
    )
    version_form = BrandAssetVersionForm(request.POST or None, request.FILES or None)
    if request.method == "POST":
        if request.POST.get("action") == "metadata" and form.is_valid():
            updated = form.save(commit=False)
            updated.updated_by = request.user
            updated.save()
            messages.success(request, "Logo-Metadaten gespeichert.")
            return redirect("asset-edit", asset_id=asset.id)
        if request.POST.get("action") == "version" and version_form.is_valid():
            try:
                add_asset_version(
                    asset=asset,
                    organization=request.organization,
                    user=request.user,
                    upload=version_form.cleaned_data["file"],
                )
            except ValidationError as exc:
                version_form.add_error("file", exc)
            else:
                messages.success(request, "Neue Logo-Version gespeichert.")
                return redirect("asset-edit", asset_id=asset.id)
    return render(
        request,
        "organizations/assets/edit.html",
        {"asset": asset, "form": form, "version_form": version_form},
    )


@login_required
def asset_preview(request: HttpRequest, version_id) -> FileResponse:
    version = get_object_or_404(
        BrandAssetVersion.objects.filter(
            organization_id=request.organization_context.organization_id
        ),
        pk=version_id,
    )
    if not version.preview_file:
        raise Http404
    response = FileResponse(version.preview_file.open("rb"), content_type="image/png")
    response["Content-Disposition"] = 'inline; filename="logo-preview.png"'
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return response
