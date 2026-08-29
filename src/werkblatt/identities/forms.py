from django import forms

from .models import User


class UserSettingsForm(forms.ModelForm):
    preferred_language = forms.ChoiceField(
        choices=(("de", "Deutsch"),),
        label="Sprache",
        help_text="Weitere Sprachen werden angeboten, sobald die Übersetzung vollständig ist.",
    )

    class Meta:
        model = User
        fields = ["preferred_language", "theme"]
        labels = {"theme": "Darstellung"}
        widgets = {"theme": forms.RadioSelect()}
