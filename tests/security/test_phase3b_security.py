import io
import os
import socket
import subprocess
import sys
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from werkblatt.documentation.models import DocumentTemplate
from werkblatt.documentation.template_forms import AssetPlacementForm, WorkshopTemplateForm
from werkblatt.documentation.templates_service import save_template
from werkblatt.documents.rendering import render_attendance_sheet
from werkblatt.documents.storage import WebDavConfigurationError, validate_webdav_target
from werkblatt.identities.models import Membership
from werkblatt.organizations.assets import create_asset, validate_asset_upload
from werkblatt.organizations.models import BrandAsset, Organization
from werkblatt.workshops.models import Workshop

pytestmark = [pytest.mark.django_db, pytest.mark.security]


def png_upload(name="logo.png", size=(32, 16), content_type="image/png"):
    output = io.BytesIO()
    Image.new("RGBA", size, "#00545a").save(output, format="PNG")
    return SimpleUploadedFile(name, output.getvalue(), content_type=content_type)


@pytest.fixture
def tenants(settings, tmp_path):
    settings.DEFAULT_ORGANIZATION_SLUG = "tenant-a"
    settings.MEDIA_ROOT = tmp_path / "media"
    a = Organization.objects.create(slug="tenant-a", name="Tenant A")
    b = Organization.objects.create(slug="tenant-b", name="Tenant B")
    admin_a = get_user_model().objects.create_user(username="admin-a")
    user_a = get_user_model().objects.create_user(username="user-a")
    admin_b = get_user_model().objects.create_user(username="admin-b")
    for organization, user, role in [
        (a, admin_a, Membership.Role.ORGANIZATION_ADMIN),
        (a, user_a, Membership.Role.WORKSHOP_USER),
        (b, admin_b, Membership.Role.ORGANIZATION_ADMIN),
    ]:
        Membership.objects.create(organization=organization, user=user, role=role)
    workshop_b = Workshop.objects.create(
        organization=b,
        source_type=Workshop.SourceType.NATIVE,
        title="Fremder Workshop",
        starts_at=timezone.now(),
        location="Bremen",
    )
    return a, b, admin_a, user_a, admin_b, workshop_b


def template_data(name="Vorlage B"):
    return {
        "name": name,
        "project_title": "Projekt",
        "subtitle": "",
        "funding_text": "",
        "attendance_text": "Teilnahme bestätigt.",
        "status": DocumentTemplate.Status.ACTIVE,
        "is_default": True,
    }


def output_rows():
    return [
        {
            "kind": "attendance_sheet",
            "display_name": "Teilnahmeliste",
            "enabled": True,
            "include_participant_names": True,
            "include_signature_column": True,
            "include_statistics": False,
            "include_report": False,
            "include_facilitators": False,
        }
    ]


def test_unauthenticated_and_superuser_without_membership_get_no_internal_data(tenants):
    _, _, _, _, _, workshop_b = tenants
    client = Client()
    assert client.get(reverse("asset-list")).status_code == 302
    assert client.get(reverse("template-list")).status_code == 302
    assert client.get(reverse("documentation-detail", args=[workshop_b.id])).status_code == 302

    superuser = get_user_model().objects.create_superuser(username="platform", password="secret")
    client.force_login(superuser)
    assert client.get(reverse("asset-list")).status_code == 403


def test_workshop_user_cannot_use_admin_services(tenants):
    a, _, _, user_a, _, _ = tenants
    with pytest.raises(ValidationError):
        create_asset(
            organization=a,
            user=user_a,
            display_name="Unzulässig",
            default_role=BrandAsset.Role.OTHER,
            upload=png_upload(),
        )
    with pytest.raises(PermissionDenied):
        save_template(
            organization=a,
            user=user_a,
            template=None,
            template_data=template_data("Unzulässig"),
            assets=[],
            outputs=output_rows(),
            fields=[],
        )


def test_foreign_ids_are_absent_from_forms_and_endpoints(tenants):
    a, b, admin_a, _, admin_b, workshop_b = tenants
    foreign_asset = create_asset(
        organization=b,
        user=admin_b,
        display_name="Fremdes Logo",
        default_role=BrandAsset.Role.FUNDER,
        upload=png_upload(),
    )
    foreign_template = save_template(
        organization=b,
        user=admin_b,
        template=None,
        template_data=template_data(),
        assets=[],
        outputs=output_rows(),
        fields=[],
    )
    assert (
        not AssetPlacementForm(organization_id=a.id)
        .fields["asset"]
        .queryset.filter(pk=foreign_asset.pk)
    )
    assert (
        not WorkshopTemplateForm(organization_id=a.id)
        .fields["template"]
        .queryset.filter(pk=foreign_template.pk)
    )

    client = Client()
    client.force_login(admin_a)
    for method, url in [
        (client.get, reverse("asset-edit", args=[foreign_asset.id])),
        (client.post, reverse("asset-edit", args=[foreign_asset.id])),
        (client.get, reverse("asset-preview", args=[foreign_asset.current_version_id])),
        (client.get, reverse("template-edit", args=[foreign_template.id])),
        (client.post, reverse("template-duplicate", args=[foreign_template.id])),
        (client.get, reverse("documentation-detail", args=[workshop_b.id])),
    ]:
        assert method(url).status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><script/></svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" onload="x"/>',
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><foreignObject/></svg>',
        b'<!DOCTYPE svg [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><svg>&xxe;</svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><image href="https://evil.invalid/x"/></svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><path style="fill:url(http://evil.invalid)"/></svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><animate/></svg>',
        b'<SvG xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><ScRiPt/></SvG>',
    ],
)
def test_adversarial_svg_is_rejected(payload):
    upload = SimpleUploadedFile("attack.svg", payload, content_type="image/svg+xml")
    with pytest.raises(ValidationError):
        validate_asset_upload(upload)


def test_deep_svg_is_rejected():
    payload = (
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
        + b"<g>" * 70
        + b"</g>" * 70
        + b"</svg>"
    )
    with pytest.raises(ValidationError, match="zu komplex"):
        validate_asset_upload(SimpleUploadedFile("deep.svg", payload))


def test_png_content_sniffing_limits_and_trailing_data():
    validate_asset_upload(png_upload(name="wrong.svg", content_type="text/plain"))
    valid = png_upload().read()
    with pytest.raises(ValidationError, match="angehängte Daten"):
        validate_asset_upload(SimpleUploadedFile("polyglot.png", valid + b"<script>x</script>"))
    with pytest.raises(ValidationError, match="zu groß"):
        validate_asset_upload(png_upload(size=(8001, 1)))
    with pytest.raises(ValidationError, match="10 MiB"):
        validate_asset_upload(
            SimpleUploadedFile("large.png", b"\x89PNG\r\n\x1a\n" + b"0" * (10 * 1024 * 1024))
        )


@pytest.mark.parametrize(
    "filename",
    ["../../foo.svg", "..\\foo.png", "/etc/passwd", "..∕unicode.png", "x" * 400 + ".png"],
)
def test_user_filename_never_controls_storage_path(tenants, filename):
    a, _, admin_a, _, _, _ = tenants
    asset = create_asset(
        organization=a,
        user=admin_a,
        display_name=f"Logo {BrandAsset.objects.count()}",
        default_role=BrandAsset.Role.OTHER,
        upload=png_upload(name=filename),
    )
    path = asset.current_version.original_file.name
    assert ".." not in path
    assert "/etc/" not in path
    assert filename not in path
    assert str(a.id) in path


def test_cross_tenant_render_is_denied(tenants):
    a, b, admin_a, _, admin_b, workshop_b = tenants
    template = save_template(
        organization=b,
        user=admin_b,
        template=None,
        template_data=template_data(),
        assets=[],
        outputs=output_rows(),
        fields=[],
    )
    from werkblatt.documentation.models import Documentation, WorkshopTemplateAssignment

    assignment = WorkshopTemplateAssignment.objects.create(
        organization=b,
        workshop=workshop_b,
        template=template,
        template_version=template.current_version,
        assigned_by=admin_b,
    )
    documentation = Documentation.objects.create(
        organization=b,
        workshop=workshop_b,
        template_assignment=assignment,
        created_by=admin_b,
        updated_by=admin_b,
    )
    with pytest.raises(PermissionDenied):
        render_attendance_sheet(documentation, admin_a)


def test_webdav_trust_modes_and_credentials(settings):
    settings.WEBDAV_TRUST_MODE = "hosted"
    settings.WEBDAV_ALLOWED_HOSTS = set()
    private_dns = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
    with patch("socket.getaddrinfo", return_value=private_dns):
        with pytest.raises(WebDavConfigurationError):
            validate_webdav_target("https://nextcloud.internal/remote.php/dav")
    settings.WEBDAV_TRUST_MODE = "self_hosted"
    assert validate_webdav_target("https://nextcloud.internal/remote.php/dav").startswith("https")
    with pytest.raises(WebDavConfigurationError):
        validate_webdav_target("https://user:secret@nextcloud.internal/dav")


def test_production_rejects_development_secret():
    environment = os.environ.copy()
    environment["DJANGO_DEBUG"] = "false"
    environment.pop("DJANGO_SECRET_KEY", None)
    result = subprocess.run(
        [sys.executable, "-c", "import config.settings"],
        cwd=os.getcwd(),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "DJANGO_SECRET_KEY" in result.stderr


def test_secret_can_be_read_from_file(tmp_path):
    secret_file = tmp_path / "secret"
    secret_file.write_text("file-secret\n", encoding="utf-8")
    environment = os.environ.copy()
    environment["DJANGO_DEBUG"] = "true"
    environment.pop("TEST_SECRET", None)
    environment["TEST_SECRET_FILE"] = str(secret_file)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from config.settings import secret; print(secret('TEST_SECRET'))",
        ],
        cwd=os.getcwd(),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "file-secret"


def test_secret_rejects_direct_and_file_values(tmp_path):
    secret_file = tmp_path / "secret"
    secret_file.write_text("file-secret", encoding="utf-8")
    environment = os.environ.copy()
    environment["DJANGO_DEBUG"] = "true"
    environment["TEST_SECRET"] = "direct-secret"
    environment["TEST_SECRET_FILE"] = str(secret_file)
    result = subprocess.run(
        [sys.executable, "-c", "from config.settings import secret; secret('TEST_SECRET')"],
        cwd=os.getcwd(),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "dürfen nicht gemeinsam gesetzt sein" in result.stderr
    assert "direct-secret" not in result.stderr
    assert "file-secret" not in result.stderr
