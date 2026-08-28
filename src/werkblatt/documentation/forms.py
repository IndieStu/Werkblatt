from django import forms
from django.forms import inlineformset_factory

from .models import Documentation, Facilitator, ParticipantEntry


class DocumentationForm(forms.ModelForm):
    expected_version = forms.IntegerField(widget=forms.HiddenInput)

    class Meta:
        model = Documentation
        fields = ["conducted_as_planned", "report"]
        labels = {
            "conducted_as_planned": "Workshop durchgeführt wie geplant",
            "report": "Kurzbericht / Feedback",
        }
        widgets = {
            "report": forms.Textarea(
                attrs={
                    "rows": 6,
                    "placeholder": "Was lief gut? Gab es Abweichungen oder wichtige Hinweise?",
                }
            )
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.fields["expected_version"].initial = self.instance.version


class ParticipantForm(forms.ModelForm):
    class Meta:
        model = ParticipantEntry
        fields = ["display_name", "present"]
        labels = {"display_name": "Name", "present": "Anwesend"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound and self.instance._state.adding:
            self.fields["present"].initial = True


class FacilitatorForm(forms.ModelForm):
    class Meta:
        model = Facilitator
        fields = ["display_name"]
        labels = {"display_name": "Name"}


ParticipantFormSet = inlineformset_factory(
    Documentation,
    ParticipantEntry,
    form=ParticipantForm,
    extra=2,
    can_delete=True,
)

FacilitatorFormSet = inlineformset_factory(
    Documentation,
    Facilitator,
    form=FacilitatorForm,
    extra=2,
    can_delete=True,
)
