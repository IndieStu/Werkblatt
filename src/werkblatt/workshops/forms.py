from django import forms

from .models import (
    PretixEventCreationPreset,
    PretixEventRule,
    PretixFundingText,
    Workshop,
)


def _valid_pretix_identifier(value):
    return bool(value) and all(
        character.isascii() and (character.isalnum() or character in "-_") for character in value
    )


class NativeWorkshopForm(forms.ModelForm):
    class Meta:
        model = Workshop
        fields = ["title", "starts_at", "ends_at", "location"]
        labels = {
            "title": "Titel",
            "starts_at": "Beginn",
            "ends_at": "Ende",
            "location": "Ort",
        }
        widgets = {
            "starts_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            "ends_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["starts_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["ends_at"].input_formats = ["%Y-%m-%dT%H:%M"]

    def clean(self):
        cleaned = super().clean()
        starts_at = cleaned.get("starts_at")
        ends_at = cleaned.get("ends_at")
        if starts_at and ends_at and ends_at <= starts_at:
            self.add_error("ends_at", "Das Ende muss nach dem Beginn liegen.")
        return cleaned


class WorkshopFilterForm(forms.Form):
    STATE_CHOICES = [
        ("", "Alle Bearbeitungsstände"),
        ("upcoming", "Anstehend"),
        ("undocumented", "Nicht dokumentiert"),
        ("draft", "Entwurf"),
        ("finalized", "Abgeschlossen"),
        ("not_required", "Keine Dokumentation erforderlich"),
        ("cancelled", "Abgesagt"),
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


class PretixEventCreationPresetForm(forms.ModelForm):
    def __init__(self, *args, organization_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization_id = organization_id

    class Meta:
        model = PretixEventCreationPreset
        fields = [
            "display_name",
            "template_event_slug",
            "primary_item_internal_name",
            "child_item_internal_name",
            "active",
        ]
        labels = {
            "display_name": "Bezeichnung",
            "template_event_slug": "Slug der Pretix-Vorlage",
            "primary_item_internal_name": "Interner Name des Standardtickets",
            "child_item_internal_name": "Interner Name der Kinderanmeldung",
            "active": "Für neue Workshops auswählbar",
        }
        help_texts = {
            "template_event_slug": "Die Vorlage muss in Pretix inaktiv und nicht öffentlich sein.",
            "primary_item_internal_name": "Nicht der sichtbare Ticketname.",
            "child_item_internal_name": "Nicht der sichtbare Ticketname.",
        }

    def clean(self):
        cleaned = super().clean()
        for field in (
            "template_event_slug",
            "primary_item_internal_name",
            "child_item_internal_name",
        ):
            value = cleaned.get(field, "").strip()
            if value and not _valid_pretix_identifier(value):
                self.add_error(field, "Nur ASCII-Buchstaben, Zahlen, Bindestrich und _ verwenden.")
            cleaned[field] = value
        if cleaned.get("primary_item_internal_name") == cleaned.get("child_item_internal_name"):
            self.add_error(
                "child_item_internal_name",
                "Standardticket und Kinderanmeldung benötigen unterschiedliche interne Namen.",
            )
        name = cleaned.get("display_name", "").strip()
        cleaned["display_name"] = name
        if name and (
            PretixEventCreationPreset.objects.filter(
                organization_id=self.organization_id,
                display_name=name,
            )
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            self.add_error("display_name", "Diese Bezeichnung wird bereits verwendet.")
        slug = cleaned.get("template_event_slug", "")
        if slug and (
            PretixEventCreationPreset.objects.filter(
                organization_id=self.organization_id,
                template_event_slug=slug,
            )
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            self.add_error("template_event_slug", "Diese Pretix-Vorlage wird bereits verwendet.")
        return cleaned


class PretixFundingTextForm(forms.ModelForm):
    def __init__(self, *args, organization_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization_id = organization_id

    class Meta:
        model = PretixFundingText
        fields = ["display_name", "text", "active"]
        labels = {
            "display_name": "Bezeichnung",
            "text": "Fördertext",
            "active": "Für neue Workshops auswählbar",
        }
        widgets = {"text": forms.Textarea(attrs={"rows": 8})}

    def clean(self):
        cleaned = super().clean()
        name = cleaned.get("display_name", "").strip()
        text = cleaned.get("text", "").strip()
        cleaned["display_name"] = name
        cleaned["text"] = text
        if name and (
            PretixFundingText.objects.filter(
                organization_id=self.organization_id,
                display_name=name,
            )
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            self.add_error("display_name", "Diese Bezeichnung wird bereits verwendet.")
        return cleaned


class PretixWorkshopCreationForm(forms.Form):
    preset = forms.ModelChoiceField(
        queryset=PretixEventCreationPreset.objects.none(),
        label="Workshop-Standard",
    )
    title = forms.CharField(max_length=300, label="Titel")
    starts_at = forms.DateTimeField(
        label="Beginn",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        input_formats=["%Y-%m-%dT%H:%M"],
    )
    ends_at = forms.DateTimeField(
        required=False,
        label="Ende",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        input_formats=["%Y-%m-%dT%H:%M"],
    )
    location = forms.CharField(required=False, max_length=300, label="Ort")
    description = forms.CharField(
        required=False,
        max_length=10000,
        label="Beschreibung",
        widget=forms.Textarea(attrs={"rows": 8}),
    )
    funding_text = forms.ModelChoiceField(
        queryset=PretixFundingText.objects.none(),
        required=False,
        empty_label="Kein Fördertext",
        label="Fördertext",
    )
    capacity = forms.IntegerField(min_value=1, max_value=10000, label="Teilnehmendenzahl")
    child_registration_enabled = forms.BooleanField(
        required=False,
        label="Anmeldung für Kinder anbieten",
    )

    def __init__(self, *args, organization_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["preset"].queryset = PretixEventCreationPreset.objects.filter(
            organization_id=organization_id,
            active=True,
        )
        self.fields["funding_text"].queryset = PretixFundingText.objects.filter(
            organization_id=organization_id,
            active=True,
        )

    def clean(self):
        cleaned = super().clean()
        starts_at = cleaned.get("starts_at")
        ends_at = cleaned.get("ends_at")
        if starts_at and ends_at and ends_at <= starts_at:
            self.add_error("ends_at", "Das Ende muss nach dem Beginn liegen.")
        return cleaned
