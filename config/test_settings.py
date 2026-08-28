import os

os.environ.setdefault("DJANGO_DEBUG", "true")

from .settings import *  # noqa: E402,F403

DEBUG = True
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
