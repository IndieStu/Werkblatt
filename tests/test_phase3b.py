import io
import sys
import types
from copy import deepcopy

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from pypdf import PdfReader

from werkblatt.documentation.models import (
    DocumentationCustomFieldValue,
    DocumentTemplate,
    TemplateCustomFieldDefinition,
    TemplateOutputDefinition,
    WorkshopTemplateAssignment,
)
from werkblatt.documentation.services import (
    build_snapshot,
    finalize_documentation,
    get_or_create_documentation,
    snapshot_sha256,
)
from werkblatt.documentation.templates_service import (
    duplicate_template,
    save_template,
    template_initial,
)
from werkblatt.documents.models import GeneratedDocument
from werkblatt.documents.rendering import render_attendance_sheet, render_revision_outputs
from werkblatt.documents.storage import store_via_webdav
from werkblatt.identities.models import Membership
from werkblatt.organizations.assets import add_asset_version, create_asset, validate_asset_upload
from werkblatt.organizations.models import BrandAsset, Organization
from werkblatt.workshops.models import Workshop


def png_upload(name="logo.png", color="#00545a"):
    output = io.BytesIO()
    Image.new("RGBA", (320, 120), color).save(output, format="PNG")
    return SimpleUploadedFile(name, output.getvalue(), content_type="image/png")


@pytest.fixture
def phase3_setup(db, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.DEFAULT_ORGANIZATION_SLUG = "zircula"
    organization = Organization.objects.create(slug="zircula", name="Zircula e.V.")
    admin = get_user_model().objects.create_user(username="admin", display_name="Admin Person")
    workshop_user = get_user_model().objects.create_user(username="workshop-user")
    Membership.objects.create(
        organization=organization,
        user=admin,
        role=Membership.Role.ORGANIZATION_ADMIN,
    )
    Membership.objects.create(
        organization=organization,
        user=workshop_user,
        role=Membership.Role.WORKSHOP_USER,
    )
    workshop = Workshop.objects.create(
        organization=organization,
        source_type=Workshop.SourceType.NATIVE,
        title="Klimawerkstatt",
        starts_at=timezone.now(),
        location="Bremerhaven",
    )
    return organization, admin, workshop_user, workshop


def template_data(name="Fördernachweis"):
    return {
        "name": name,
        "project_title": "Klimaschutz im Alltag",
        "subtitle": "",
        "funding_text": "",
        "attendance_text": "Teilnahme wird mit Unterschrift bestätigt.",
        "status": DocumentTemplate.Status.ACTIVE,
        "is_default": True,
    }


def output_rows():
    return [
        {
            "kind": TemplateOutputDefinition.Kind.FINAL_REPORT,
            "display_name": "Abschlussdokument",
            "enabled": True,
            "include_participant_names": True,
            "include_signature_column": False,
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
    ]


def gender_fields():
    return [
        {
            "label": label,
            "help_text": "Freiwillige aggregierte Angabe",
            "field_type": TemplateCustomFieldDefinition.FieldType.INTEGER,
            "required": False,
            "presentation": TemplateCustomFieldDefinition.Presentation.AGGREGATE_STATISTIC,
            "choice_options_text": "",
            "include_final_report": True,
            "include_attendance_sheet": False,
            "include_anonymized_report": False,
        }
        for label in ["Männlich", "Weiblich", "Divers", "Keine Angabe"]
    ]


@pytest.mark.django_db
def test_png_asset_is_versioned_and_old_hash_stays_immutable(phase3_setup):
    organization, admin, _, _ = phase3_setup
    asset = create_asset(
        organization=organization,
        user=admin,
        display_name="Dieckell Stiftung",
        default_role=BrandAsset.Role.FUNDER,
        upload=png_upload(color="#00529b"),
    )
    first = asset.current_version
    first_hash = first.sha256
    second = add_asset_version(
        asset=asset,
        organization=organization,
        user=admin,
        upload=png_upload(color="#777777"),
    )
    first.refresh_from_db()
    asset.refresh_from_db()
    assert second.number == 2
    assert asset.current_version == second
    assert first.sha256 == first_hash
    with pytest.raises(ValueError):
        first.save()


@pytest.mark.django_db
def test_unsafe_svg_is_rejected_without_asset(phase3_setup):
    organization, admin, _, _ = phase3_setup
    unsafe = SimpleUploadedFile(
        "unsafe.svg",
        b'<svg viewBox="0 0 10 10"><script>alert(1)</script></svg>',
        content_type="image/svg+xml",
    )
    with pytest.raises(ValidationError, match="aktive oder externe"):
        create_asset(
            organization=organization,
            user=admin,
            display_name="Unsicher",
            default_role=BrandAsset.Role.OTHER,
            upload=unsafe,
        )
    assert not BrandAsset.objects.filter(display_name="Unsicher").exists()


@pytest.mark.django_db
def test_safe_svg_is_stored_with_generated_png_preview(phase3_setup, monkeypatch):
    organization, admin, _, _ = phase3_setup
    preview = png_upload().read()
    fake_cairosvg = types.ModuleType("cairosvg")
    fake_cairosvg.svg2png = lambda **_kwargs: preview
    monkeypatch.setitem(sys.modules, "cairosvg", fake_cairosvg)
    upload = SimpleUploadedFile(
        "zircula.svg",
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 40">'
        b'<path d="M0 0h100v40H0z" fill="#00545a"/></svg>',
        content_type="image/svg+xml",
    )

    asset = create_asset(
        organization=organization,
        user=admin,
        display_name="Zircula",
        default_role=BrandAsset.Role.ORGANIZATION,
        upload=upload,
    )

    assert asset.current_version.media_type == "image/svg+xml"
    assert asset.current_version.width == 100
    assert asset.current_version.height == 40
    with Image.open(asset.current_version.preview_file.path) as image:
        assert image.format == "PNG"


@pytest.mark.django_db
def test_fake_png_is_rejected(phase3_setup):
    upload = SimpleUploadedFile("fake.png", b"not really an image", content_type="image/png")
    with pytest.raises(ValidationError, match="ausschließlich SVG und PNG"):
        validate_asset_upload(upload)


@pytest.mark.django_db
def test_workshop_user_cannot_manage_assets_but_cannot_leak_foreign_preview(phase3_setup):
    organization, admin, workshop_user, _ = phase3_setup
    asset = create_asset(
        organization=organization,
        user=admin,
        display_name="Zircula",
        default_role=BrandAsset.Role.ORGANIZATION,
        upload=png_upload(),
    )
    client = Client()
    client.force_login(workshop_user)
    assert client.get(reverse("asset-list")).status_code == 403

    other = Organization.objects.create(slug="other", name="Andere Organisation")
    other_admin = get_user_model().objects.create_user(username="other-admin")
    Membership.objects.create(
        organization=other,
        user=other_admin,
        role=Membership.Role.ORGANIZATION_ADMIN,
    )
    foreign = create_asset(
        organization=other,
        user=other_admin,
        display_name="Fremd",
        default_role=BrandAsset.Role.OTHER,
        upload=png_upload(),
    )
    response = client.get(reverse("asset-preview", args=[foreign.current_version_id]))
    assert response.status_code == 404
    assert asset.current_version_id != foreign.current_version_id


@pytest.mark.django_db
def test_output_privacy_is_per_output_and_gender_is_custom_fields(phase3_setup):
    organization, admin, _, _ = phase3_setup
    outputs = output_rows()
    outputs.append(
        {
            "kind": TemplateOutputDefinition.Kind.ANONYMIZED_REPORT,
            "display_name": "Anonymisierte Fassung",
            "enabled": True,
            "include_participant_names": True,
            "include_signature_column": False,
            "include_statistics": True,
            "include_report": True,
            "include_facilitators": False,
        }
    )
    template = save_template(
        organization=organization,
        user=admin,
        template=None,
        template_data=template_data(),
        assets=[],
        outputs=outputs,
        fields=gender_fields(),
    )
    final = template.current_version.outputs.get(kind=TemplateOutputDefinition.Kind.FINAL_REPORT)
    attendance = template.current_version.outputs.get(
        kind=TemplateOutputDefinition.Kind.ATTENDANCE_SHEET
    )
    anonymized = template.current_version.outputs.get(
        kind=TemplateOutputDefinition.Kind.ANONYMIZED_REPORT
    )
    assert final.include_participant_names is True
    assert attendance.include_participant_names is True
    assert anonymized.include_participant_names is False
    assert template.current_version.custom_fields.count() == 4
    assert not hasattr(template, "include_participant_names")


@pytest.mark.django_db
def test_new_asset_version_requires_conscious_template_update(phase3_setup):
    organization, admin, _, _ = phase3_setup
    asset = create_asset(
        organization=organization,
        user=admin,
        display_name="Förderlogo",
        default_role=BrandAsset.Role.FUNDER,
        upload=png_upload(color="#111111"),
    )
    first_asset_version = asset.current_version
    placement = {
        "asset": asset,
        "role": BrandAsset.Role.FUNDER,
        "zone": "funding_footer",
        "show_funded_by_label": True,
    }
    template = save_template(
        organization=organization,
        user=admin,
        template=None,
        template_data=template_data(),
        assets=[placement],
        outputs=output_rows(),
        fields=[],
    )
    add_asset_version(
        asset=asset,
        organization=organization,
        user=admin,
        upload=png_upload(color="#222222"),
    )
    asset.refresh_from_db()
    initial = template_initial(template)
    assert initial["assets"][0]["has_newer_version"] is True

    template = save_template(
        organization=organization,
        user=admin,
        template=template,
        template_data=initial["template"],
        assets=initial["assets"],
        outputs=initial["outputs"],
        fields=initial["fields"],
    )
    assert template.current_version.asset_placements.get().asset_version == first_asset_version

    newer = template_initial(template)
    newer["assets"][0]["use_current_version"] = True
    template = save_template(
        organization=organization,
        user=admin,
        template=template,
        template_data=newer["template"],
        assets=newer["assets"],
        outputs=newer["outputs"],
        fields=newer["fields"],
    )
    assert template.current_version.asset_placements.get().asset_version == asset.current_version


@pytest.mark.django_db
def test_duplicate_template_is_independent_complete_copy(phase3_setup):
    organization, admin, _, _ = phase3_setup
    original = save_template(
        organization=organization,
        user=admin,
        template=None,
        template_data=template_data(),
        assets=[],
        outputs=output_rows(),
        fields=gender_fields(),
    )
    duplicate = duplicate_template(template=original, organization=organization, user=admin)
    assert duplicate.id != original.id
    assert duplicate.current_version_id != original.current_version_id
    assert duplicate.current_version.outputs.count() == original.current_version.outputs.count()
    assert (
        duplicate.current_version.custom_fields.count()
        == original.current_version.custom_fields.count()
    )
    duplicate_data = template_initial(duplicate)
    duplicate_data["template"]["project_title"] = "Unabhängig geändert"
    save_template(
        organization=organization,
        user=admin,
        template=duplicate,
        template_data=duplicate_data["template"],
        assets=duplicate_data["assets"],
        outputs=duplicate_data["outputs"],
        fields=duplicate_data["fields"],
    )
    original.refresh_from_db()
    assert original.current_version.project_title == "Klimaschutz im Alltag"


@pytest.mark.django_db
def test_snapshot_freezes_template_output_assets_and_custom_fields(phase3_setup):
    organization, admin, _, workshop = phase3_setup
    asset = create_asset(
        organization=organization,
        user=admin,
        display_name="FHB",
        default_role=BrandAsset.Role.FUNDER,
        upload=png_upload(color="#ff0000"),
    )
    template = save_template(
        organization=organization,
        user=admin,
        template=None,
        template_data=template_data(),
        assets=[
            {
                "asset": asset,
                "role": BrandAsset.Role.FUNDER,
                "zone": "funding_footer",
                "show_funded_by_label": True,
            }
        ],
        outputs=output_rows(),
        fields=gender_fields(),
    )
    assignment = WorkshopTemplateAssignment.objects.create(
        organization=organization,
        workshop=workshop,
        template=template,
        template_version=template.current_version,
        assigned_by=admin,
    )
    documentation = get_or_create_documentation(workshop=workshop, user=admin)
    documentation.template_assignment = assignment
    documentation.save(update_fields=["template_assignment"])
    first_field = template.current_version.custom_fields.first()
    DocumentationCustomFieldValue.objects.create(
        organization=organization,
        documentation=documentation,
        field_stable_key=first_field.stable_key,
        value=4,
        updated_by=admin,
    )
    snapshot = build_snapshot(documentation)
    frozen = deepcopy(snapshot["template"])
    add_asset_version(
        asset=asset,
        organization=organization,
        user=admin,
        upload=png_upload(color="#00ff00"),
    )
    assert snapshot["template"] == frozen
    assert snapshot["template"]["outputs"][0]["include_participant_names"] is True
    assert snapshot["template"]["assets"][0]["sha256"] != asset.current_version.sha256


@pytest.mark.django_db
def test_cross_tenant_template_duplicate_is_denied(phase3_setup):
    organization, admin, _, _ = phase3_setup
    template = save_template(
        organization=organization,
        user=admin,
        template=None,
        template_data=template_data(),
        assets=[],
        outputs=output_rows(),
        fields=[],
    )
    other = Organization.objects.create(slug="other-duplicate", name="Andere")
    with pytest.raises(PermissionDenied):
        duplicate_template(template=template, organization=other, user=admin)


@pytest.mark.django_db
def test_revision_output_rendering_is_idempotent_and_download_is_tenant_scoped(
    phase3_setup, monkeypatch
):
    organization, admin, _, workshop = phase3_setup
    template = save_template(
        organization=organization,
        user=admin,
        template=None,
        template_data=template_data(),
        assets=[],
        outputs=output_rows(),
        fields=[],
    )
    assignment = WorkshopTemplateAssignment.objects.create(
        organization=organization,
        workshop=workshop,
        template=template,
        template_version=template.current_version,
        assigned_by=admin,
    )
    documentation = get_or_create_documentation(workshop=workshop, user=admin)
    documentation.template_assignment = assignment
    documentation.save(update_fields=["template_assignment"])
    revision = finalize_documentation(
        documentation_id=documentation.id,
        organization_id=organization.id,
        user=admin,
        expected_version=documentation.version,
    )

    class FakeHTML:
        def __init__(self, **_kwargs):
            pass

        def write_pdf(self):
            return b"%PDF-1.4\n% synthetic test renderer\n%%EOF"

    fake_weasyprint = types.ModuleType("weasyprint")
    fake_weasyprint.HTML = FakeHTML
    fake_weasyprint.default_url_fetcher = lambda *_args, **_kwargs: {}
    monkeypatch.setitem(sys.modules, "weasyprint", fake_weasyprint)
    first = render_revision_outputs(revision, admin)
    second = render_revision_outputs(revision, admin)
    assert len(first) == 1
    assert first[0].id == second[0].id
    assert first[0].status == GeneratedDocument.Status.RENDERED
    assert GeneratedDocument.objects.count() == 1

    other = Organization.objects.create(slug="download-other", name="Andere")
    other_user = get_user_model().objects.create_user(username="download-other")
    Membership.objects.create(
        organization=other,
        user=other_user,
        role=Membership.Role.WORKSHOP_USER,
    )
    client = Client()
    client.force_login(other_user)
    with override_settings(DEFAULT_ORGANIZATION_SLUG="download-other"):
        response = client.get(reverse("document-download", args=[first[0].id]))
    assert response.status_code == 404


@pytest.mark.django_db
def test_attendance_sheet_creates_readable_pdf_with_local_fallback(phase3_setup):
    organization, admin, _, workshop = phase3_setup
    template = save_template(
        organization=organization,
        user=admin,
        template=None,
        template_data=template_data(),
        assets=[],
        outputs=output_rows(),
        fields=[],
    )
    assignment = WorkshopTemplateAssignment.objects.create(
        organization=organization,
        workshop=workshop,
        template=template,
        template_version=template.current_version,
        assigned_by=admin,
    )
    documentation = get_or_create_documentation(workshop=workshop, user=admin)
    documentation.template_assignment = assignment
    documentation.save(update_fields=["template_assignment"])

    generated = render_attendance_sheet(documentation, admin)

    reader = PdfReader(generated.pdf_file.path)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert len(reader.pages) >= 1
    assert "Klimawerkstatt" in text
    assert "Bremerhaven" in text
    assert generated.renderer_version in {"weasyprint-69/v1", "reportlab-fallback/v1"}


@pytest.mark.django_db(transaction=True)
def test_webdav_storage_runs_outside_atomic_block_and_is_retryable(
    phase3_setup, monkeypatch, settings, caplog
):
    organization, admin, _, workshop = phase3_setup
    template = save_template(
        organization=organization,
        user=admin,
        template=None,
        template_data=template_data(),
        assets=[],
        outputs=output_rows(),
        fields=[],
    )
    assignment = WorkshopTemplateAssignment.objects.create(
        organization=organization,
        workshop=workshop,
        template=template,
        template_version=template.current_version,
        assigned_by=admin,
    )
    documentation = get_or_create_documentation(workshop=workshop, user=admin)
    documentation.template_assignment = assignment
    documentation.save(update_fields=["template_assignment"])
    generated = render_attendance_sheet(documentation, admin)
    settings.WEBDAV_BASE_URL = "https://cloud.example.invalid/remote.php/dav/files/werkblatt"
    settings.WEBDAV_USERNAME = "werkblatt"
    settings.WEBDAV_PASSWORD = "SECRET-MARKER-WEBDAV-9f86d081"
    settings.WEBDAV_ROOT = "Werkblatt"
    settings.WEBDAV_TRUST_MODE = "self_hosted"

    class FakeResponse:
        status_code = 201

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def request(self, *_args, **_kwargs):
            assert connection.in_atomic_block is False
            return FakeResponse()

        def put(self, *_args, **_kwargs):
            assert connection.in_atomic_block is False
            return FakeResponse()

    monkeypatch.setattr("werkblatt.documents.storage.httpx.Client", FakeClient)
    stored = store_via_webdav(generated)
    assert stored.status == GeneratedDocument.Status.STORED
    assert stored.storage_key.endswith(".pdf")
    stored.status = GeneratedDocument.Status.RENDERED
    stored.save(update_fields=["status"])

    class FailingClient(FakeClient):
        def put(self, *_args, **_kwargs):
            assert connection.in_atomic_block is False
            raise TimeoutError("temporary failure")

    monkeypatch.setattr("werkblatt.documents.storage.httpx.Client", FailingClient)
    failed = store_via_webdav(stored)
    assert failed.status == GeneratedDocument.Status.STORAGE_FAILED
    assert failed.last_error_class == "TimeoutError"
    assert settings.WEBDAV_PASSWORD not in caplog.text
    assert settings.WEBDAV_PASSWORD not in failed.storage_key
    assert settings.WEBDAV_PASSWORD not in failed.last_error_class

    monkeypatch.setattr("werkblatt.documents.storage.httpx.Client", FakeClient)
    retried = store_via_webdav(failed)
    assert retried.status == GeneratedDocument.Status.STORED
    assert retried.last_error_class == ""


@pytest.mark.django_db
def test_historical_render_uses_frozen_asset_template_and_escaped_text(phase3_setup, monkeypatch):
    organization, admin, _, workshop = phase3_setup
    asset = create_asset(
        organization=organization,
        user=admin,
        display_name="Historisches Logo",
        default_role=BrandAsset.Role.ORGANIZATION,
        upload=png_upload(color="#111111"),
    )
    first_asset_version = asset.current_version
    template = save_template(
        organization=organization,
        user=admin,
        template=None,
        template_data=template_data(name="Historische Vorlage"),
        assets=[
            {
                "asset": asset,
                "role": BrandAsset.Role.ORGANIZATION,
                "zone": "header",
                "show_funded_by_label": False,
            }
        ],
        outputs=output_rows(),
        fields=gender_fields()[:1],
    )
    assignment = WorkshopTemplateAssignment.objects.create(
        organization=organization,
        workshop=workshop,
        template=template,
        template_version=template.current_version,
        assigned_by=admin,
    )
    documentation = get_or_create_documentation(workshop=workshop, user=admin)
    documentation.template_assignment = assignment
    documentation.report = '<script>alert("marker")</script> sehr_lang_' + "x" * 500
    documentation.save(update_fields=["template_assignment", "report"])
    revision = finalize_documentation(
        documentation_id=documentation.id,
        organization_id=organization.id,
        user=admin,
        expected_version=documentation.version,
    )
    frozen_snapshot = deepcopy(revision.snapshot)
    frozen_hash = revision.snapshot_sha256

    add_asset_version(
        asset=asset,
        organization=organization,
        user=admin,
        upload=png_upload(color="#222222"),
    )
    changed = template_initial(template)
    changed["template"]["project_title"] = "Neuer Projektname"
    changed["assets"][0]["use_current_version"] = True
    save_template(
        organization=organization,
        user=admin,
        template=template,
        template_data=changed["template"],
        assets=changed["assets"],
        outputs=changed["outputs"],
        fields=changed["fields"],
    )
    Workshop.objects.filter(pk=workshop.pk).update(title="Später geänderter Workshop")
    admin.display_name = "Später geänderter Admin"
    admin.save(update_fields=["display_name"])

    captured = {}

    class FakeHTML:
        def __init__(self, **kwargs):
            captured["html"] = kwargs["string"]

        def write_pdf(self):
            return b"%PDF-1.4\n% historical renderer\n%%EOF"

    fake_weasyprint = types.ModuleType("weasyprint")
    fake_weasyprint.HTML = FakeHTML
    fake_weasyprint.default_url_fetcher = lambda *_args, **_kwargs: {}
    monkeypatch.setitem(sys.modules, "weasyprint", fake_weasyprint)
    monkeypatch.setattr("werkblatt.documents.rendering.find_library", lambda _name: "available")
    render_revision_outputs(revision, admin)

    revision.refresh_from_db()
    assert revision.snapshot == frozen_snapshot
    assert revision.snapshot_sha256 == frozen_hash
    assert str(first_asset_version.id) in captured["html"]
    assert str(asset.current_version.id) not in captured["html"]
    assert "Klimawerkstatt" in captured["html"]
    assert "Später geänderter Workshop" not in captured["html"]
    assert "Admin Person" in captured["html"]
    assert "Später geänderter Admin" not in captured["html"]
    assert "<script>" not in captured["html"]
    assert "&lt;script&gt;" in captured["html"]


def test_snapshot_hash_is_canonical_and_deterministic():
    first = {"date": "2026-08-28", "decimal": "4.20", "boolean": True, "choice": "divers"}
    second = {"choice": "divers", "boolean": True, "decimal": "4.20", "date": "2026-08-28"}
    assert snapshot_sha256(first) == snapshot_sha256(second)
