from django import forms
from django.forms import formset_factory

from werkblatt.organizations.models import BrandAsset

from .models import (
    DocumentTemplate,
    TemplateAssetPlacement,
    TemplateCustomFieldDefinition,
    TemplateOutputDefinition,
)


class WorkshopTemplateForm(forms.Form):
    template = forms.ModelChoiceField(
        queryset=DocumentTemplate.objects.none(), label="Dokumentvorlage"
    )

    def __init__(self, *args, organization_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["template"].queryset = DocumentTemplate.objects.for_organization(
            organization_id
        ).filter(status=DocumentTemplate.Status.ACTIVE, current_version__isnull=False)


class DocumentationCustomFieldsForm(forms.Form):
    def __init__(self, *args, definitions=(), values=None, **kwargs):
        super().__init__(*args, **kwargs)
        values = values or {}
        for definition in definitions:
            key = f"custom_{definition.stable_key}"
            common = {
                "label": definition.label,
                "help_text": definition.help_text,
                "required": definition.required,
                "initial": values.get(str(definition.stable_key), definition.default_value),
            }
            if definition.field_type == TemplateCustomFieldDefinition.FieldType.SHORT_TEXT:
                field = forms.CharField(max_length=500, **common)
            elif definition.field_type == TemplateCustomFieldDefinition.FieldType.LONG_TEXT:
                field = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}), **common)
            elif definition.field_type == TemplateCustomFieldDefinition.FieldType.INTEGER:
                field = forms.IntegerField(min_value=0, **common)
            elif definition.field_type == TemplateCustomFieldDefinition.FieldType.DECIMAL:
                field = forms.DecimalField(max_digits=12, decimal_places=2, **common)
            elif definition.field_type == TemplateCustomFieldDefinition.FieldType.BOOLEAN:
                common["required"] = False
                field = forms.BooleanField(**common)
            elif definition.field_type == TemplateCustomFieldDefinition.FieldType.CHOICE:
                field = forms.ChoiceField(
                    choices=[(item["value"], item["label"]) for item in definition.choice_options],
                    **common,
                )
            else:
                field = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), **common)
            self.fields[key] = field

    def values_by_stable_key(self):
        values = {}
        for name, value in self.cleaned_data.items():
            if not name.startswith("custom_"):
                continue
            if hasattr(value, "isoformat"):
                value = value.isoformat()
            elif value is not None and not isinstance(value, (str, int, float, bool)):
                value = str(value)
            values[name.removeprefix("custom_")] = value
        return values


class TemplateForm(forms.Form):
    name = forms.CharField(max_length=200, label="Vorlagenname")
    project_title = forms.CharField(max_length=300, required=False, label="Projekt / Programm")
    subtitle = forms.CharField(max_length=300, required=False, label="Untertitel")
    funding_text = forms.CharField(
        max_length=2000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Fördertext",
    )
    attendance_text = forms.CharField(
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Text auf der Teilnahmeliste",
    )
    status = forms.ChoiceField(choices=DocumentTemplate.Status, label="Status")
    is_default = forms.BooleanField(required=False, label="Standardvorlage")


class AssetPlacementForm(forms.Form):
    asset = forms.ModelChoiceField(queryset=BrandAsset.objects.none(), required=False, label="Logo")
    asset_version_id = forms.UUIDField(required=False, widget=forms.HiddenInput)
    role = forms.ChoiceField(choices=BrandAsset.Role, required=False, label="Rolle")
    zone = forms.ChoiceField(
        choices=TemplateAssetPlacement.Zone, required=False, label="Dokumentbereich"
    )
    show_funded_by_label = forms.BooleanField(required=False, label="‚Gefördert durch‘ anzeigen")
    use_current_version = forms.BooleanField(
        required=False, initial=False, label="Auf aktuelle Logo-Version aktualisieren"
    )

    def __init__(self, *args, organization_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["asset"].queryset = BrandAsset.objects.for_organization(organization_id).filter(
            status=BrandAsset.Status.ACTIVE, current_version__isnull=False
        )


AssetPlacementFormSet = formset_factory(AssetPlacementForm, extra=2, can_delete=True)


class OutputDefinitionForm(forms.Form):
    kind = forms.ChoiceField(
        choices=[("", "---------"), *TemplateOutputDefinition.Kind.choices],
        required=False,
        label="Ausgabe",
    )
    display_name = forms.CharField(max_length=200, required=False, label="Bezeichnung")
    enabled = forms.BooleanField(required=False, initial=True, label="Aktiv")
    include_participant_names = forms.BooleanField(required=False, label="Klarnamen ausgeben")
    include_signature_column = forms.BooleanField(required=False, label="Unterschriftsspalte")
    include_statistics = forms.BooleanField(required=False, initial=True, label="Statistik")
    include_report = forms.BooleanField(required=False, initial=True, label="Bericht")
    include_facilitators = forms.BooleanField(required=False, initial=True, label="Durchführende")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("kind") == TemplateOutputDefinition.Kind.ANONYMIZED_REPORT:
            cleaned["include_participant_names"] = False
        return cleaned


OutputDefinitionFormSet = formset_factory(OutputDefinitionForm, extra=1, can_delete=True)


class CustomFieldDefinitionForm(forms.Form):
    stable_key = forms.UUIDField(required=False, widget=forms.HiddenInput)
    label = forms.CharField(max_length=200, required=False, label="Feldname")
    help_text = forms.CharField(max_length=500, required=False, label="Hilfetext")
    field_type = forms.ChoiceField(
        choices=TemplateCustomFieldDefinition.FieldType, required=False, label="Feldtyp"
    )
    required = forms.BooleanField(required=False, label="Pflichtfeld")
    presentation = forms.ChoiceField(
        choices=TemplateCustomFieldDefinition.Presentation,
        required=False,
        label="Darstellung",
    )
    choice_options_text = forms.CharField(
        required=False, label="Auswahloptionen", help_text="Eine Option pro Zeile"
    )
    include_final_report = forms.BooleanField(required=False, label="Im Abschlussdokument")
    include_attendance_sheet = forms.BooleanField(required=False, label="In Teilnahmeliste")
    include_anonymized_report = forms.BooleanField(
        required=False, label="In anonymisierter Fassung"
    )


CustomFieldDefinitionFormSet = formset_factory(CustomFieldDefinitionForm, extra=2, can_delete=True)
