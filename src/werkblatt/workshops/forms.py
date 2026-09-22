from django import forms

from .models import PretixEventRule, Workshop


class WorkshopFilterForm(forms.Form):
    STATE_CHOICES = [
        ("", "Alle Bearbeitungsstände"),
        ("upcoming", "Anstehend"),
        ("undocumented", "Nicht dokumentiert"),
        ("draft", "Entwurf"),
        ("finalized", "Abgeschlossen"),
        ("not_required", "Keine Dokumentation erforderlich"),
    ]
    VISIBILITY_CHOICES = [
        (Workshop.Visibility.ACTIVE, "Sichtbar"),
        (Workshop.Visibility.HIDDEN, "Ausgeblendet"),
        ("all", "Alle"),
    ]

    q = forms.CharField(required=False, label="Suche")
    state = forms.ChoiceField(required=False, choices=STATE_CHOICES, label="Status")
    visibility = forms.ChoiceField(
        required=False, choices=VISIBILITY_CHOICES, initial=Workshop.Visibility.ACTIVE
    )
    date_from = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"}), label="Von"
    )
    date_to = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"}), label="Bis"
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("date_from") and cleaned.get("date_to"):
            if cleaned["date_from"] > cleaned["date_to"]:
                raise forms.ValidationError("Das Von-Datum darf nicht nach dem Bis-Datum liegen.")
        return cleaned


class WorkshopRequirementForm(forms.Form):
    documentation_requirement = forms.ChoiceField(
        choices=Workshop.DocumentationRequirement, label="Dokumentationspflicht"
    )
    reason = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Begründung",
    )

    def clean(self):
        cleaned = super().clean()
        if (
            cleaned.get("documentation_requirement")
            == Workshop.DocumentationRequirement.NOT_REQUIRED
            and not cleaned.get("reason", "").strip()
        ):
            self.add_error("reason", "Eine Begründung ist erforderlich.")
        return cleaned


class PretixEventRuleForm(forms.ModelForm):
    def __init__(self, *args, organization_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization_id = organization_id

    class Meta:
        model = PretixEventRule
        fields = [
            "event_slug",
            "display_name",
            "import_enabled",
            "documentation_requirement",
            "reason",
        ]
        labels = {
            "event_slug": "Pretix-Event-Slug",
            "display_name": "Bezeichnung",
            "import_enabled": "Termine importieren",
            "documentation_requirement": "Dokumentationspflicht",
            "reason": "Begründung",
        }
        widgets = {"reason": forms.Textarea(attrs={"rows": 3})}

    def clean_event_slug(self):
        slug = self.cleaned_data["event_slug"].strip()
        if not slug or not all(char.isalnum() or char in "-_" for char in slug):
            raise forms.ValidationError("Der Pretix-Event-Slug ist ungültig.")
        if (
            PretixEventRule.objects.filter(organization_id=self.organization_id, event_slug=slug)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise forms.ValidationError(
                "Für diesen Pretix-Event-Slug existiert bereits eine Regel."
            )
        return slug

    def clean(self):
        cleaned = super().clean()
        if (
            not cleaned.get("import_enabled", True)
            or cleaned.get("documentation_requirement")
            == Workshop.DocumentationRequirement.NOT_REQUIRED
        ) and not cleaned.get("reason", "").strip():
            self.add_error("reason", "Für diese Ausnahme ist eine Begründung erforderlich.")
        return cleaned
