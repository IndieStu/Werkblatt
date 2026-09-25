from django import forms

from .models import User


class UserSettingsForm(forms.ModelForm):
    preferred_language = forms.ChoiceField(
        choices=(("de", "Deutsch"),),
        label="Sprache",
        help_text="Weitere Sprachen werden angeboten, sobald die Übersetzung vollständig ist.",
    )
    preferred_workshop_view = forms.ChoiceField(
        choices=User.WorkshopView.choices,
        label="Standardansicht der Workshops",
        widget=forms.RadioSelect(),
        required=False,
    )

    class Meta:
        model = User
        fields = ["preferred_language", "theme", "preferred_workshop_view"]
        labels = {
            "theme": "Darstellung",
            "preferred_workshop_view": "Standardansicht der Workshops",
        }
        widgets = {
            "theme": forms.RadioSelect(),
        }

    def clean_preferred_workshop_view(self):
        return (
            self.cleaned_data.get("preferred_workshop_view")
            or self.instance.preferred_workshop_view
            or User.WorkshopView.CALENDAR
        )
