from django import forms

from .models import BrandAsset, Organization


class OrganizationProfileForm(forms.ModelForm):
    website = forms.URLField(required=False, assume_scheme="https", label="Website")

    class Meta:
        model = Organization
        fields = ["name", "address", "website", "email", "phone"]
        labels = {
            "name": "Organisationsname",
            "address": "Anschrift",
            "website": "Website",
            "email": "E-Mail",
            "phone": "Telefon",
        }


class BrandAssetUploadForm(forms.Form):
    display_name = forms.CharField(max_length=200, label="Anzeigename")
    default_role = forms.ChoiceField(choices=BrandAsset.Role, label="Kategorie")
    file = forms.FileField(label="SVG- oder PNG-Datei")


class BrandAssetEditForm(forms.ModelForm):
    class Meta:
        model = BrandAsset
        fields = ["display_name", "default_role", "status"]
        labels = {
            "display_name": "Anzeigename",
            "default_role": "Kategorie",
            "status": "Status",
        }


class BrandAssetVersionForm(forms.Form):
    file = forms.FileField(label="Neue SVG- oder PNG-Version")
