import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from werkblatt.identities.models import Membership
from werkblatt.organizations.models import Organization
from werkblatt.workshops.models import Workshop


@pytest.mark.django_db
def test_workshop_list_never_leaks_other_organization(settings):
    settings.DEFAULT_ORGANIZATION_SLUG = "zircula"
    user = get_user_model().objects.create_user(username="pilot", password="test-password")
    zircula = Organization.objects.create(slug="zircula", name="Zircula e.V.")
    other = Organization.objects.create(slug="other", name="Andere Organisation")
    Membership.objects.create(organization=zircula, user=user, role=Membership.Role.WORKSHOP_USER)
    own = Workshop.objects.create(
        organization=zircula,
        source_type=Workshop.SourceType.PRETIX,
        external_reference="own",
        title="Eigener Workshop",
        starts_at=timezone.now(),
    )
    foreign = Workshop.objects.create(
        organization=other,
        source_type=Workshop.SourceType.NATIVE,
        title="Fremder Workshop",
        starts_at=timezone.now(),
    )

    client = Client()
    client.force_login(user)
    response = client.get(reverse("workshop-list"))

    assert response.status_code == 200
    assert own.title.encode() in response.content
    assert foreign.title.encode() not in response.content


@pytest.mark.django_db
def test_user_without_membership_is_denied(settings):
    settings.DEFAULT_ORGANIZATION_SLUG = "zircula"
    Organization.objects.create(slug="zircula", name="Zircula e.V.")
    user = get_user_model().objects.create_user(username="outsider", password="test-password")
    client = Client()
    client.force_login(user)
    response = client.get(reverse("workshop-list"))
    assert response.status_code == 403
