from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from werkblatt.identities.models import Membership

from .assets import add_asset_version, create_asset
from .forms import (
    BrandAssetEditForm,
    BrandAssetUploadForm,
    BrandAssetVersionForm,
    OrganizationProfileForm,
)
from .models import BrandAsset, BrandAssetVersion


def _require_admin(request: HttpRequest) -> None:
    if not request.user.memberships.filter(
        organization_id=request.organization_context.organization_id,
        role=Membership.Role.ORGANIZATION_ADMIN,
        status=Membership.Status.ACTIVE,
    ).exists():
        raise PermissionDenied("Nur Organization Admins dürfen diese Einstellungen ändern.")


@login_required
def settings_home(request: HttpRequest) -> HttpResponse:
    _require_admin(request)
    return render(request, "organizations/settings_home.html")


@login_required
def organization_profile(request: HttpRequest) -> HttpResponse:
    _require_admin(request)
    organization = request.organization
    form = OrganizationProfileForm(request.POST or None, instance=organization)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Organisationsprofil gespeichert.")
        return redirect("organization-profile")
    return render(request, "organizations/profile.html", {"form": form})


@login_required
def asset_list(request: HttpRequest) -> HttpResponse:
    _require_admin(request)
    assets = BrandAsset.objects.for_organization(
        request.organization_context.organization_id
    ).select_related("current_version")
    return render(request, "organizations/assets/list.html", {"assets": assets})


@login_required
def asset_create(request: HttpRequest) -> HttpResponse:
    _require_admin(request)
    form = BrandAssetUploadForm(request.POST or None, request.FILES or None)
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
    _require_admin(request)
    asset = get_object_or_404(
        BrandAsset.objects.for_organization(request.organization_context.organization_id),
        pk=asset_id,
    )
    form = BrandAssetEditForm(request.POST or None, instance=asset)
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
