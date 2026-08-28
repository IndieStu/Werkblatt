import io
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connection
from django.utils import timezone
from PIL import Image

from werkblatt.documentation.models import Documentation, DocumentTemplate, Facilitator
from werkblatt.documentation.services import finalize_documentation
from werkblatt.documentation.templates_service import save_template, template_initial
from werkblatt.identities.models import Membership
from werkblatt.organizations.assets import add_asset_version, create_asset
from werkblatt.organizations.models import BrandAsset, Organization
from werkblatt.workshops.models import Workshop

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.security]


def png_upload(color):
    output = io.BytesIO()
    Image.new("RGBA", (32, 16), color).save(output, format="PNG")
    return SimpleUploadedFile("logo.png", output.getvalue(), content_type="image/png")


def output_rows():
    return [
        {
            "kind": "final_report",
            "display_name": "Abschluss",
            "enabled": True,
            "include_participant_names": False,
            "include_signature_column": False,
            "include_statistics": True,
            "include_report": True,
            "include_facilitators": True,
        }
    ]


def setup_admin():
    organization = Organization.objects.create(slug="concurrency", name="Concurrency")
    admin = get_user_model().objects.create_user(username="concurrency-admin")
    Membership.objects.create(
        organization=organization,
        user=admin,
        role=Membership.Role.ORGANIZATION_ADMIN,
    )
    return organization, admin


def require_postgresql():
    if connection.vendor != "postgresql":
        pytest.skip("Echte Sperrsemantik wird im PostgreSQL-CI-Job geprüft")


def test_concurrent_asset_versions_are_serialized():
    require_postgresql()
    organization, admin = setup_admin()
    asset = create_asset(
        organization=organization,
        user=admin,
        display_name="Logo",
        default_role=BrandAsset.Role.OTHER,
        upload=png_upload("#111111"),
    )
    barrier = Barrier(2)

    def worker(color):
        close_old_connections()
        local_org = Organization.objects.get(pk=organization.pk)
        local_admin = get_user_model().objects.get(pk=admin.pk)
        local_asset = BrandAsset.objects.get(pk=asset.pk)
        barrier.wait()
        version = add_asset_version(
            asset=local_asset,
            organization=local_org,
            user=local_admin,
            upload=png_upload(color),
        )
        close_old_connections()
        return version.number

    with ThreadPoolExecutor(max_workers=2) as pool:
        numbers = sorted(pool.map(worker, ["#222222", "#333333"]))
    assert numbers == [2, 3]
    assert list(asset.versions.order_by("number").values_list("number", flat=True)) == [1, 2, 3]


def test_concurrent_template_updates_keep_both_versions():
    require_postgresql()
    organization, admin = setup_admin()
    data = {
        "name": "Vorlage",
        "project_title": "V1",
        "subtitle": "",
        "funding_text": "",
        "attendance_text": "Teilnahme",
        "status": DocumentTemplate.Status.ACTIVE,
        "is_default": True,
    }
    template = save_template(
        organization=organization,
        user=admin,
        template=None,
        template_data=data,
        assets=[],
        outputs=output_rows(),
        fields=[],
    )
    barrier = Barrier(2)

    def worker(title):
        close_old_connections()
        local_org = Organization.objects.get(pk=organization.pk)
        local_admin = get_user_model().objects.get(pk=admin.pk)
        local_template = DocumentTemplate.objects.get(pk=template.pk)
        initial = template_initial(local_template)
        initial["template"]["project_title"] = title
        barrier.wait()
        result = save_template(
            organization=local_org,
            user=local_admin,
            template=local_template,
            template_data=initial["template"],
            assets=initial["assets"],
            outputs=initial["outputs"],
            fields=initial["fields"],
        )
        close_old_connections()
        return result.current_version.number

    with ThreadPoolExecutor(max_workers=2) as pool:
        numbers = sorted(pool.map(worker, ["V2-A", "V2-B"]))
    assert numbers == [2, 3]
    assert set(template.versions.values_list("project_title", flat=True)) == {"V1", "V2-A", "V2-B"}


def test_concurrent_finalization_creates_one_revision():
    require_postgresql()
    organization, admin = setup_admin()
    workshop = Workshop.objects.create(
        organization=organization,
        source_type=Workshop.SourceType.NATIVE,
        title="Parallel",
        starts_at=timezone.now(),
    )
    documentation = Documentation.objects.create(
        organization=organization,
        workshop=workshop,
        created_by=admin,
        updated_by=admin,
    )
    Facilitator.objects.create(
        organization=organization,
        documentation=documentation,
        display_name="Leitung",
    )
    barrier = Barrier(2)

    def worker(_index):
        close_old_connections()
        local_admin = get_user_model().objects.get(pk=admin.pk)
        barrier.wait()
        try:
            revision = finalize_documentation(
                documentation_id=documentation.pk,
                organization_id=organization.pk,
                user=local_admin,
                expected_version=documentation.version,
            )
            result = ("created", revision.number)
        except Exception as exc:
            result = ("rejected", type(exc).__name__)
        close_old_connections()
        return result

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, range(2)))
    assert sum(result[0] == "created" for result in results) == 1
    assert documentation.revisions.count() == 1
