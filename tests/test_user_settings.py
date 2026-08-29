import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from werkblatt.identities.models import Membership
from werkblatt.organizations.models import Organization


@pytest.fixture
def settings_user(settings):
    settings.DEFAULT_ORGANIZATION_SLUG = "example"
    organization = Organization.objects.create(slug="example", name="Example Organization")
    user = get_user_model().objects.create_user(username="pilot", password="test-password")
    Membership.objects.create(
        organization=organization,
        user=user,
        role=Membership.Role.WORKSHOP_USER,
    )
    return organization, user


@pytest.mark.django_db
def test_user_can_save_personal_theme_without_changing_organization(settings_user):
    organization, user = settings_user
    original_name = organization.name
    client = Client()
    client.force_login(user)

    response = client.post(
        reverse("user-settings"),
        {"preferred_language": "de", "theme": "dark"},
    )

    assert response.status_code == 302
    user.refresh_from_db()
    organization.refresh_from_db()
    assert user.preferred_language == "de"
    assert user.theme == "dark"
    assert organization.name == original_name


@pytest.mark.django_db
@pytest.mark.parametrize("theme", ["light", "dark", "system"])
def test_saved_theme_is_rendered_on_html_root(settings_user, theme):
    _, user = settings_user
    user.theme = theme
    user.save(update_fields=["theme"])
    client = Client()
    client.force_login(user)

    response = client.get(reverse("user-settings"))

    assert response.status_code == 200
    assert f'data-theme="{theme}"'.encode() in response.content
    assert b"Nutzungsanleitung" in response.content
    assert b"Quellcode auf GitHub" in response.content


@pytest.mark.django_db
def test_workshop_user_cannot_access_organization_administration(settings_user):
    _, user = settings_user
    client = Client()
    client.force_login(user)

    response = client.get(reverse("settings-home"))

    assert response.status_code == 403


def test_dark_mode_uses_corporate_tokens_and_system_color_scheme():
    tokens = (settings.BASE_DIR / "static/werkblatt/css/tokens.css").read_text()
    app_css = (settings.BASE_DIR / "static/werkblatt/css/app.css").read_text()

    assert ':root[data-theme="dark"]' in tokens
    assert "@media (prefers-color-scheme: dark)" in tokens
    assert ':root[data-theme="system"]' in tokens
    assert "--brand-petrol-dark: #a7dce0" in tokens
    assert "var(--color-panel)" in app_css
    assert "var(--color-field)" in app_css
    assert "var(--color-on-primary)" in app_css
