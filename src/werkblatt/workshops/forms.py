from django import forms
from django.db.models import Q
from django.utils import timezone

from .models import (
    OpenWorkshopAttendance,
    OpenWorkshopSeries,
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
    OTHER_LOCATION = "__other__"

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
    registration_deadline = forms.DateTimeField(
        required=False,
        label="Anmeldung möglich bis",
        help_text="Optional. Danach schließt Pretix die Anmeldung automatisch.",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        input_formats=["%Y-%m-%dT%H:%M"],
    )
    location_choice = forms.ChoiceField(required=False, label="Bekannter Ort")
    location = forms.CharField(
        required=False,
        max_length=300,
        label="Anderer Ort",
        help_text="Nur ausfüllen, wenn der gewünschte Ort nicht in der Auswahl steht.",
    )
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

    def __init__(self, *args, organization_id=None, location_choices=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.known_locations = tuple(dict.fromkeys(location_choices))
        self.fields["location_choice"].choices = [
            ("", "Ort auswählen"),
            *((location, location) for location in self.known_locations),
            (self.OTHER_LOCATION, "Anderer Ort"),
        ]
        self.fields["location_choice"].widget.attrs["aria-controls"] = "location-custom-field"
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
        registration_deadline = cleaned.get("registration_deadline")
        if starts_at and registration_deadline and registration_deadline >= starts_at:
            self.add_error(
                "registration_deadline",
                "Der Anmeldeschluss muss vor dem Workshopbeginn liegen.",
            )
        selected_location = cleaned.get("location_choice", "")
        custom_location = cleaned.get("location", "").strip()
        if selected_location in self.known_locations:
            cleaned["location"] = selected_location
        elif selected_location == self.OTHER_LOCATION:
            if not custom_location:
                self.add_error("location", "Bitte den anderen Ort eintragen.")
            cleaned["location"] = custom_location
        elif custom_location:
            cleaned["location"] = custom_location
        else:
            cleaned["location"] = ""
        return cleaned


class OpenWorkshopSeriesForm(forms.ModelForm):
    class Meta:
        model = OpenWorkshopSeries
        fields = ["name", "location", "schedule_description", "active"]
        labels = {
            "name": "Bezeichnung",
            "location": "Ort",
            "schedule_description": "Wiederkehrender Termin",
            "active": "Für neue Erfassungen auswählbar",
        }
        help_texts = {
            "schedule_description": "Zum Beispiel: Jeden Dienstag, 15 bis 18 Uhr.",
        }

    def __init__(self, *args, organization_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization_id = organization_id

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if (
            OpenWorkshopSeries.objects.filter(
                organization_id=self.organization_id,
                name=name,
            )
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise forms.ValidationError("Diese Bezeichnung wird bereits verwendet.")
        return name


class OpenWorkshopAttendanceForm(forms.ModelForm):
    class Meta:
        model = OpenWorkshopAttendance
        fields = [
            "series",
            "occurred_on",
            "total",
            "female",
            "male",
            "diverse",
            "unspecified",
            "note",
        ]
        labels = {
            "series": "Offene Werkstatt",
            "occurred_on": "Datum",
            "total": "Teilnehmende insgesamt",
            "female": "Weiblich",
            "male": "Männlich",
            "diverse": "Divers",
            "unspecified": "Keine Angabe",
            "note": "Interne Notiz",
        }
        widgets = {
            "occurred_on": forms.DateInput(attrs={"type": "date"}),
            "note": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, organization_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization_id = organization_id
        selectable = Q(active=True)
        if self.instance.pk and self.instance.series_id:
            selectable |= Q(pk=self.instance.series_id)
        self.fields["series"].queryset = OpenWorkshopSeries.objects.filter(
            selectable,
            organization_id=organization_id,
        )
        for field in ("total", "female", "male", "diverse", "unspecified"):
            self.fields[field].widget.attrs["min"] = 0

    def clean(self):
        cleaned = super().clean()
        series = cleaned.get("series")
        if series and series.organization_id != self.organization_id:
            raise forms.ValidationError("Die Reihe gehört nicht zur aktiven Organisation.")
        values = [cleaned.get(field) for field in ("female", "male", "diverse", "unspecified")]
        total = cleaned.get("total")
        if total is not None and all(value is not None for value in values):
            if sum(values) != total:
                raise forms.ValidationError(
                    "Die Geschlechterangaben müssen zusammen der Gesamtzahl entsprechen."
                )
        occurred_on = cleaned.get("occurred_on")
        if occurred_on and occurred_on > timezone.localdate():
            self.add_error("occurred_on", "Zukünftige Termine können nicht erfasst werden.")
        if (
            series
            and occurred_on
            and (
                OpenWorkshopAttendance.objects.filter(
                    organization_id=self.organization_id,
                    series=series,
                    occurred_on=occurred_on,
                )
                .exclude(pk=self.instance.pk)
                .exists()
            )
        ):
            self.add_error("occurred_on", "Für diese Reihe ist das Datum bereits erfasst.")
        return cleaned


class OpenWorkshopStatisticsFilterForm(forms.Form):
    date_from = forms.DateField(
        required=False,
        label="Von",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    date_to = forms.DateField(
        required=False,
        label="Bis",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    series = forms.ModelChoiceField(
        queryset=OpenWorkshopSeries.objects.none(),
        required=False,
        empty_label="Alle offenen Werkstätten",
        label="Reihe",
    )

    def __init__(self, *args, organization_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["series"].queryset = OpenWorkshopSeries.objects.filter(
            organization_id=organization_id
        )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("date_from") and cleaned.get("date_to"):
            if cleaned["date_from"] > cleaned["date_to"]:
                raise forms.ValidationError("Das Von-Datum darf nicht nach dem Bis-Datum liegen.")
        return cleaned
