import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction

from werkblatt.identities.models import Membership
from werkblatt.organizations.models import BrandAssetVersion

from .models import (
    DocumentTemplate,
    DocumentTemplateVersion,
    TemplateAssetPlacement,
    TemplateCustomFieldDefinition,
    TemplateOutputDefinition,
)


def _require_template_admin(organization, user) -> None:
    if (
        not user.is_authenticated
        or not user.memberships.filter(
            organization=organization,
            role=Membership.Role.ORGANIZATION_ADMIN,
            status=Membership.Status.ACTIVE,
        ).exists()
    ):
        raise PermissionDenied("Nur Organization Admins dürfen Dokumentvorlagen verwalten.")


def template_initial(template):
    version = template.current_version
    return {
        "template": {
            "name": template.name,
            "project_title": version.project_title,
            "subtitle": version.subtitle,
            "funding_text": version.funding_text,
            "attendance_text": version.attendance_text,
            "status": template.status,
            "is_default": template.is_default,
        },
        "assets": [
            {
                "asset": placement.asset_version.asset,
                "asset_version_id": placement.asset_version_id,
                "role": placement.role,
                "zone": placement.zone,
                "show_funded_by_label": placement.show_funded_by_label,
                "use_current_version": False,
                "has_newer_version": (
                    placement.asset_version_id != placement.asset_version.asset.current_version_id
                ),
            }
            for placement in version.asset_placements.select_related(
                "asset_version__asset__current_version"
            )
        ],
        "outputs": [
            {
                "kind": output.kind,
                "display_name": output.display_name,
                "enabled": output.enabled,
                "include_participant_names": output.include_participant_names,
                "include_signature_column": output.include_signature_column,
                "include_statistics": output.include_statistics,
                "include_report": output.include_report,
                "include_facilitators": output.include_facilitators,
            }
            for output in version.outputs.all()
        ],
        "fields": [
            {
                "stable_key": field.stable_key,
                "label": field.label,
                "help_text": field.help_text,
                "field_type": field.field_type,
                "required": field.required,
                "presentation": field.presentation,
                "choice_options_text": "\n".join(
                    item.get("label", item.get("value", "")) for item in field.choice_options
                ),
                "include_final_report": (
                    TemplateOutputDefinition.Kind.FINAL_REPORT in field.include_in_output_kinds
                ),
                "include_attendance_sheet": (
                    TemplateOutputDefinition.Kind.ATTENDANCE_SHEET in field.include_in_output_kinds
                ),
                "include_anonymized_report": (
                    TemplateOutputDefinition.Kind.ANONYMIZED_REPORT in field.include_in_output_kinds
                ),
            }
            for field in version.custom_fields.all()
        ],
    }


@transaction.atomic
def save_template(*, organization, user, template, template_data, assets, outputs, fields):
    _require_template_admin(organization, user)
    if template is None:
        template = DocumentTemplate.objects.create(
            organization=organization,
            name=template_data["name"].strip(),
            status=template_data["status"],
            is_default=False,
            created_by=user,
            updated_by=user,
        )
    elif template.organization_id != organization.id:
        raise PermissionDenied
    else:
        template = DocumentTemplate.objects.select_for_update().get(
            pk=template.pk, organization=organization
        )
    if template_data["is_default"]:
        DocumentTemplate.objects.for_organization(organization.id).exclude(pk=template.pk).update(
            is_default=False
        )
    number = (template.versions.aggregate(maximum=models.Max("number"))["maximum"] or 0) + 1
    version = DocumentTemplateVersion.objects.create(
        organization=organization,
        template=template,
        number=number,
        project_title=template_data["project_title"].strip(),
        subtitle=template_data["subtitle"].strip(),
        funding_text=template_data["funding_text"].strip(),
        attendance_text=template_data["attendance_text"].strip(),
        created_by=user,
    )
    for index, row in enumerate(assets):
        asset = row.get("asset")
        if not asset or row.get("DELETE"):
            continue
        if asset.organization_id != organization.id or not asset.current_version_id:
            raise ValidationError("Ungültiges Logo in der Dokumentvorlage.")
        if not row.get("zone"):
            raise ValidationError("Jedes Logo benötigt einen Dokumentbereich.")
        asset_version = asset.current_version
        previous_version_id = row.get("asset_version_id")
        if previous_version_id and not row.get("use_current_version"):
            try:
                previous_version = BrandAssetVersion.objects.get(
                    pk=previous_version_id,
                    asset=asset,
                    organization=organization,
                )
            except BrandAssetVersion.DoesNotExist as exc:
                raise ValidationError("Die bisherige Logo-Version ist ungültig.") from exc
            asset_version = previous_version
        TemplateAssetPlacement.objects.create(
            organization=organization,
            template_version=version,
            asset_version=asset_version,
            role=row["role"] or asset.default_role,
            zone=row["zone"],
            sort_order=index,
            show_funded_by_label=row["show_funded_by_label"],
            accessible_name=asset.display_name,
        )
    kinds = set()
    for index, row in enumerate(outputs):
        if not row.get("kind") or row.get("DELETE"):
            continue
        if row["kind"] in kinds:
            raise ValidationError("Jede Ausgabeart darf nur einmal vorkommen.")
        kinds.add(row["kind"])
        include_names = row["include_participant_names"]
        if row["kind"] == TemplateOutputDefinition.Kind.ANONYMIZED_REPORT:
            include_names = False
        TemplateOutputDefinition.objects.create(
            organization=organization,
            template_version=version,
            kind=row["kind"],
            display_name=row["display_name"].strip()
            or dict(TemplateOutputDefinition.Kind.choices)[row["kind"]],
            enabled=row["enabled"],
            sort_order=index,
            include_participant_names=include_names,
            include_signature_column=row["include_signature_column"],
            include_statistics=row["include_statistics"],
            include_report=row["include_report"],
            include_facilitators=row["include_facilitators"],
        )
    if not kinds:
        raise ValidationError("Mindestens eine Dokumentausgabe ist erforderlich.")
    for index, row in enumerate(fields):
        if not row.get("label") or row.get("DELETE"):
            continue
        if not row.get("field_type") or not row.get("presentation"):
            raise ValidationError("Zusatzfelder benötigen Feldtyp und Darstellung.")
        output_kinds = [
            kind
            for flag, kind in [
                ("include_final_report", TemplateOutputDefinition.Kind.FINAL_REPORT),
                ("include_attendance_sheet", TemplateOutputDefinition.Kind.ATTENDANCE_SHEET),
                ("include_anonymized_report", TemplateOutputDefinition.Kind.ANONYMIZED_REPORT),
            ]
            if row.get(flag)
        ]
        choices = [
            {"value": value.strip(), "label": value.strip()}
            for value in row.get("choice_options_text", "").splitlines()
            if value.strip()
        ]
        if row["field_type"] == TemplateCustomFieldDefinition.FieldType.CHOICE and not choices:
            raise ValidationError("Auswahlfelder benötigen mindestens eine Option.")
        TemplateCustomFieldDefinition.objects.create(
            organization=organization,
            template_version=version,
            stable_key=row.get("stable_key") or uuid.uuid4(),
            label=row["label"].strip(),
            help_text=row["help_text"].strip(),
            field_type=row["field_type"],
            required=row["required"],
            sort_order=index,
            choice_options=choices,
            presentation=row["presentation"],
            include_in_output_kinds=output_kinds,
        )
    template.name = template_data["name"].strip()
    template.status = template_data["status"]
    template.is_default = template_data["is_default"]
    template.current_version = version
    template.updated_by = user
    template.save(
        update_fields=[
            "name",
            "status",
            "is_default",
            "current_version",
            "updated_by",
            "updated_at",
        ]
    )
    return template


@transaction.atomic
def duplicate_template(*, template, organization, user):
    _require_template_admin(organization, user)
    if template.organization_id != organization.id:
        raise PermissionDenied
    data = template_initial(template)
    base_name = f"{template.name} (Kopie)"
    name = base_name
    counter = 2
    while DocumentTemplate.objects.for_organization(organization.id).filter(name=name).exists():
        name = f"{base_name} {counter}"
        counter += 1
    data["template"]["name"] = name
    data["template"]["is_default"] = False
    return save_template(
        organization=organization,
        user=user,
        template=None,
        template_data=data["template"],
        assets=data["assets"],
        outputs=data["outputs"],
        fields=data["fields"],
    )
