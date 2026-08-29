from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import UserSettingsForm
from .oidc import normalized_claims, oauth_client
from .services import provision_oidc_user


def login_page(request: HttpRequest) -> HttpResponse:
    return render(request, "identities/login.html")


def oidc_login(request: HttpRequest) -> HttpResponse:
    redirect_uri = f"{settings.PUBLIC_BASE_URL.rstrip('/')}{reverse('oidc-callback')}"
    return oauth_client().authorize_redirect(request, redirect_uri)


def oidc_callback(request: HttpRequest) -> HttpResponse:
    token = oauth_client().authorize_access_token(request)
    claims = normalized_claims(dict(token.get("userinfo") or {}))
    user = provision_oidc_user(claims)
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return redirect("workshop-list")


@require_POST
def sign_out(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect("login")


@login_required
def user_settings(request: HttpRequest) -> HttpResponse:
    form = UserSettingsForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Einstellungen gespeichert.")
        return redirect("user-settings")
    return render(request, "identities/settings.html", {"form": form})
