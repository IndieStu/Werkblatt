import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


SECRET_KEY = env("DJANGO_SECRET_KEY", "development-only-change-me")
DEBUG = env("DJANGO_DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = [v for v in env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if v]
CSRF_TRUSTED_ORIGINS = [v for v in env("DJANGO_CSRF_TRUSTED_ORIGINS").split(",") if v]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "werkblatt.organizations",
    "werkblatt.identities",
    "werkblatt.workshops",
    "werkblatt.documentation",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "werkblatt.organizations.middleware.OrganizationContextMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "werkblatt.organizations.context_processors.organization",
            ]
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"

if env("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB"),
            "USER": env("POSTGRES_USER"),
            "PASSWORD": env("POSTGRES_PASSWORD"),
            "HOST": env("POSTGRES_HOST", "db"),
            "PORT": env("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    DATABASES = {
        "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}
    }

AUTH_USER_MODEL = "identities.User"
LOGIN_URL = "/auth/login/"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "de"
TIME_ZONE = "Europe/Berlin"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DEFAULT_ORGANIZATION_SLUG = env("WERKBLATT_DEFAULT_ORGANIZATION", "zircula")
PUBLIC_BASE_URL = env("WERKBLATT_PUBLIC_BASE_URL", "http://localhost:8000")
SOFTWARE_AUTHOR_URL = env("WERKBLATT_SOFTWARE_AUTHOR_URL", "https://zircula.org")
HOSTING_PROVIDER_LABEL = env("WERKBLATT_HOSTING_PROVIDER_LABEL", "")

OIDC_DISCOVERY_URL = env("OIDC_DISCOVERY_URL")
OIDC_CLIENT_ID = env("OIDC_CLIENT_ID")
OIDC_CLIENT_SECRET = env("OIDC_CLIENT_SECRET")
OIDC_ALLOWED_GROUPS = {v.strip() for v in env("OIDC_ALLOWED_GROUPS").split(",") if v.strip()}
OIDC_ADMIN_GROUPS = {v.strip() for v in env("OIDC_ADMIN_GROUPS").split(",") if v.strip()}

PRETIX_BASE_URL = env("PRETIX_BASE_URL", "https://www.pretix.eu")
PRETIX_API_TOKEN = env("PRETIX_API_TOKEN")
PRETIX_ORGANIZER = env("PRETIX_ORGANIZER", "WERK")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 0 if DEBUG else 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
# Zircula aktiviert HSTS zentral am Reverse Proxy. IncludeSubDomains und Browser-Preload
# bleiben bewusste Infrastrukturentscheidungen und werden nicht von der App erzwungen.
SILENCED_SYSTEM_CHECKS = ["security.W005", "security.W021"]
