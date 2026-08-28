import io
import shutil

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.utils import timezone

from werkblatt.documentation.models import (
    Documentation,
    DocumentationRevision,
    DocumentTemplate,
    DocumentTemplateVersion,
)
from werkblatt.documents.models import GeneratedDocument
from werkblatt.identities.models import Membership
from werkblatt.organizations.models import BrandAsset, BrandAssetVersion, Organization
from werkblatt.workshops.models import Workshop

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.security]


def test_synthetic_database_and_private_media_restore(settings, tmp_path):
    media_root = tmp_path / "live-media"
    settings.MEDIA_ROOT = media_root
    organization = Organization.objects.create(slug="backup-org", name="Backup Organisation")
    user = get_user_model().objects.create_user(username="backup-admin")
    Membership.objects.create(
        organization=organization,
        user=user,
        role=Membership.Role.ORGANIZATION_ADMIN,
    )
    asset = BrandAsset.objects.create(
        organization=organization,
        display_name="Historisches Logo",
        default_role=BrandAsset.Role.ORGANIZATION,
        created_by=user,
        updated_by=user,
    )
    asset_version = BrandAssetVersion(
        organization=organization,
        asset=asset,
        number=1,
        original_filename="logo.png",
        media_type="image/png",
        byte_size=12,
        width=1,
        height=1,
        sha256="a" * 64,
        created_by=user,
    )
    asset_version.original_file.save("original.png", ContentFile(b"asset-original"), save=False)
    asset_version.preview_file.save("preview.png", ContentFile(b"asset-preview"), save=False)
    asset_version.save()
    asset.current_version = asset_version
    asset.save(update_fields=["current_version"])
    workshop = Workshop.objects.create(
        organization=organization,
        source_type=Workshop.SourceType.NATIVE,
        title="Backup Workshop",
        starts_at=timezone.now(),
    )
    template = DocumentTemplate.objects.create(
        organization=organization,
        name="Backup Vorlage",
        created_by=user,
        updated_by=user,
    )
    template_version = DocumentTemplateVersion.objects.create(
        organization=organization,
        template=template,
        number=1,
        created_by=user,
    )
    template.current_version = template_version
    template.save(update_fields=["current_version"])
    documentation = Documentation.objects.create(
        organization=organization,
        workshop=workshop,
        created_by=user,
        updated_by=user,
    )
    revision = DocumentationRevision.objects.create(
        organization=organization,
        documentation=documentation,
        number=1,
        snapshot={"historical_asset_version": str(asset_version.id), "custom_fields": {"x": 4}},
        snapshot_sha256="b" * 64,
        created_by=user,
    )
    generated = GeneratedDocument(
        organization=organization,
        workshop=workshop,
        revision=revision,
        template_version=template_version,
        output_kind="final_report",
        output_name="Abschluss",
        input_sha256="c" * 64,
        created_by=user,
    )
    generated.pdf_file.save("document.pdf", ContentFile(b"%PDF-synthetic-backup"), save=True)

    dump = io.StringIO()
    call_command(
        "dumpdata",
        "identities",
        "organizations",
        "workshops",
        "documentation",
        "documents",
        indent=2,
        stdout=dump,
    )
    database_backup = tmp_path / "database.json"
    database_backup.write_text(dump.getvalue(), encoding="utf-8")
    media_backup = tmp_path / "media-backup"
    shutil.copytree(media_root, media_backup)

    call_command("flush", interactive=False, verbosity=0)
    shutil.rmtree(media_root)
    shutil.copytree(media_backup, media_root)
    call_command("loaddata", database_backup, verbosity=0)

    restored_revision = DocumentationRevision.objects.get(pk=revision.pk)
    restored_asset_version = BrandAssetVersion.objects.get(pk=asset_version.pk)
    restored_document = GeneratedDocument.objects.get(pk=generated.pk)
    assert restored_revision.snapshot["custom_fields"] == {"x": 4}
    assert restored_revision.snapshot["historical_asset_version"] == str(asset_version.id)
    assert restored_asset_version.original_file.open("rb").read() == b"asset-original"
    assert restored_asset_version.preview_file.open("rb").read() == b"asset-preview"
    assert restored_document.revision_id == revision.id
    assert restored_document.pdf_file.open("rb").read() == b"%PDF-synthetic-backup"
