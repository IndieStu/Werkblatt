from django.urls import path

from . import views

urlpatterns = [
    path("login/", views.login_page, name="login"),
    path("oidc/start/", views.oidc_login, name="oidc-login"),
    path("oidc/callback/", views.oidc_callback, name="oidc-callback"),
    path("logout/", views.sign_out, name="logout"),
]
