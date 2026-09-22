import io

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from werkblatt.documentation.models import (
    DocumentTemplate,
    TemplateCustomFieldDefinition,
    TemplateOutputDefinition,
)
from werkblatt.documentation.templates_service import duplicate_template, save_template
from werkblatt.identities.models import Membership
from werkblatt.identities.policies import Capability, capabilities_for
from werkblatt.organizations.assets import add_asset_version, create_asset
from werkblatt.organizations.models import BrandAsset, Organization
from werkblatt.workshops.models import Workshop


def png_upload(name="logo.png"):
    output = io.BytesIO()
    Image.new("RGBA", (32, 16), "#00545a").save(output, format="PNG")
    return SimpleUploadedFile(name, output.getvalue(), content_type="image/png")


def template_data(name="Editor-Vorlage"):
    return {
        "name": name,
        "project_title": "Redaktionelles Projekt",
        "subtitle": "",
        "funding_text": "Gefördert durch",
        "attendance_text": "Teilnahme bestätigt.",
        "status": DocumentTemplate.Status.ACTIVE,
        "is_default": False,
    }


def output_rows():
    return [
        {
            "kind": TemplateOutputDefinition.Kind.FINAL_REPORT,
            "display_name": "Abschlussdokument",
            "enabled": True,
            "include_participant_names": False,
            "include_signature_column": False,
            "include_statistics": True,
            "include_report": True,
            "include_facilitators": True,
        }
    ]


def custom_fields():
    return [
        {
            "label": "Teilnehmende gesamt",
            "help_text": "Aggregierte Angabe",
            "field_type": TemplateCustomFieldDefinition.FieldType.INTEGER,
            "required": True,
            "presentation": TemplateCustomFieldDefinition.Presentation.AGGREGATE_STATISTIC,
            "choice_options_text": "",
            "include_final_report": True,
            "include_attendance_sheet": False,
            "include_anonymized_report": False,
        }
    ]


@pytest.fixture
def roles(db, settings, tmp_path):
    settings.DEFAULT_ORGANIZATION_SLUG = "tenant-a"
    settings.MEDIA_ROOT = tmp_path / "media"
    organization = Organization.objects.create(slug="tenant-a", name="Tenant A")
    other = Organization.objects.create(slug="tenant-b", name="Tenant B")
    users = {}
    for role in Membership.Role:
        user = get_user_model().objects.create_user(username=role.value)
        Membership.objects.create(organization=organization, user=user, role=role)
        users[role] = user
    editor_other = get_user_model().objects.create_user(username="other-editor")
    Membership.objects.create(organization=other, user=editor_other, role=Membership.Role.EDITOR)
    workshop = Workshop.objects.create(
        organization=organization,
        source_type=Workshop.SourceType.NATIVE,
        title="Synthetischer Workshop",
        starts_at=timezone.now(),
        location="Bremen",
    )
    return organization, other, users, editor_other, workshop


@pytest.mark.django_db
def test_fixed_capability_matrix(roles):
    organization, _, users, _, _ = roles
    assert capabilities_for(users[Membership.Role.WORKSHOP_USER], organization.id) == {
        Capability.DOCUMENT_WORKSHOPS
    }
    assert capabilities_for(users[Membership.Role.EDITOR], organization.id) == {
        Capability.DOCUMENT_WORKSHOPS,
        Capability.MANAGE_DOCUMENT_TEMPLATES,
        Capability.MANAGE_DOCUMENT_ASSETS,
        Capability.MANAGE_WORKSHOP_VISIBILITY,
    }
    assert capabilities_for(users[Membership.Role.ORGANIZATION_ADMIN], organization.id) == set(
        Capability
    )


@pytest.mark.django_db
def test_editor_can_document_and_manage_document_content(roles):
    organization, _, users, _, workshop = roles
    editor = users[Membership.Role.EDITOR]
    asset = create_asset(
        organization=organization,
        user=editor,
        display_name="Förderlogo",
        default_role=BrandAsset.Role.FUNDER,
        upload=png_upload(),
    )
    add_asset_version(asset=asset, organization=organization, user=editor, upload=png_upload())
    template = save_template(
        organization=organization,
        user=editor,
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
        fields=custom_fields(),
    )
    duplicate = duplicate_template(template=template, organization=organization, user=editor)
    assert duplicate.current_version.outputs.count() == 1
    assert duplicate.current_version.custom_fields.count() == 1

    client = Client()
    client.force_login(editor)
    assert client.get(reverse("documentation-detail", args=[workshop.id])).status_code == 200
    assert client.get(reverse("template-edit", args=[template.id])).status_code == 200


@pytest.mark.django_db
def test_editor_may_use_but_not_manage_organization_asset(roles):
    organization, _, users, _, _ = roles
    admin = users[Membership.Role.ORGANIZATION_ADMIN]
    editor = users[Membership.Role.EDITOR]
    organization_asset = create_asset(
        organization=organization,
        user=admin,
        display_name="Organisationslogo",
        default_role=BrandAsset.Role.ORGANIZATION,
        upload=png_upload(),
    )
    template = save_template(
        organization=organization,
        user=editor,
        template=None,
        template_data=template_data(),
        assets=[
            {
                "asset": organization_asset,
                "role": BrandAsset.Role.ORGANIZATION,
                "zone": "header",
                "show_funded_by_label": False,
            }
        ],
        outputs=output_rows(),
        fields=[],
    )
    assert template.current_version.asset_placements.get().asset_version.asset == organization_asset
    with pytest.raises(PermissionDenied):
        add_asset_version(
            asset=organization_asset,
            organization=organization,
            user=editor,
            upload=png_upload(),
        )
    with pytest.raises(PermissionDenied):
        create_asset(
            organization=organization,
            user=editor,
            display_name="Unzulässiges Organisationslogo",
            default_role=BrandAsset.Role.ORGANIZATION,
            upload=png_upload(),
        )
    client = Client()
    client.force_login(editor)
    assert client.get(reverse("asset-list")).status_code == 200
    assert client.get(reverse("asset-edit", args=[organization_asset.id])).status_code == 403


@pytest.mark.django_db
def test_editor_sees_editorial_administration_only(roles):
    organization, _, users, _, _ = roles
    editor = users[Membership.Role.EDITOR]
    client = Client()
    client.force_login(editor)
    response = client.get(reverse("settings-home"))
    body = response.content.decode()
    assert response.status_code == 200
    assert "Dokumentvorlagen" in body
    assert "Logos & Assets" in body
    assert "Organisationsprofil" not in body
    assert client.get(reverse("organization-profile")).status_code == 403
    assert Capability.MANAGE_INTEGRATIONS not in capabilities_for(editor, organization.id)
    assert Capability.MANAGE_MEMBERSHIPS not in capabilities_for(editor, organization.id)


@pytest.mark.django_db
def test_workshop_user_cannot_manage_editorial_content(roles):
    organization, _, users, _, workshop = roles
    user = users[Membership.Role.WORKSHOP_USER]
    client = Client()
    client.force_login(user)
    assert client.get(reverse("documentation-detail", args=[workshop.id])).status_code == 200
    assert client.get(reverse("template-create")).status_code == 403
    assert client.get(reverse("asset-create")).status_code == 403
    assert client.get(reverse("settings-home")).status_code == 403
    with pytest.raises(PermissionDenied):
        save_template(
            organization=organization,
            user=user,
            template=None,
            template_data=template_data(),
            assets=[],
            outputs=output_rows(),
            fields=[],
        )


@pytest.mark.django_db
def test_editor_is_strictly_tenant_scoped(roles):
    organization, other, users, editor_other, _ = roles
    editor = users[Membership.Role.EDITOR]
    foreign_asset = create_asset(
        organization=other,
        user=editor_other,
        display_name="Fremdes Förderlogo",
        default_role=BrandAsset.Role.FUNDER,
        upload=png_upload(),
    )
    foreign_template = save_template(
        organization=other,
        user=editor_other,
        template=None,
        template_data=template_data("Fremde Vorlage"),
        assets=[],
        outputs=output_rows(),
        fields=[],
    )
    client = Client()
    client.force_login(editor)
    assert client.get(reverse("asset-edit", args=[foreign_asset.id])).status_code == 404
    assert client.get(reverse("template-edit", args=[foreign_template.id])).status_code == 404
    assert client.post(reverse("template-duplicate", args=[foreign_template.id])).status_code == 404
    with pytest.raises(PermissionDenied):
        duplicate_template(template=foreign_template, organization=organization, user=editor)
