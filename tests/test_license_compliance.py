import hashlib
import re
import tomllib
from pathlib import Path

from django.conf import settings

EXPECTED_RUNTIME_DEPENDENCIES = {
    "authlib",
    "cairosvg",
    "django",
    "gunicorn",
    "httpx",
    "pillow",
    "psycopg",
    "reportlab",
    "requests",
    "weasyprint",
    "whitenoise",
}
EXPECTED_DEV_DEPENDENCIES = {
    "pip-audit",
    "pymupdf",
    "pypdf",
    "pytest",
    "pytest-django",
    "respx",
    "ruff",
}


def _dependency_name(specification):
    return re.split(r"[<>=!~\[ ]", specification, maxsplit=1)[0].lower()


def test_project_license_metadata_and_official_text_are_present():
    root = Path(settings.BASE_DIR)
    metadata = tomllib.loads((root / "pyproject.toml").read_text())

    assert metadata["project"]["license"] == "AGPL-3.0-or-later"
    assert metadata["project"]["license-files"] == ["LICENSE"]
    assert metadata["build-system"]["requires"] == ["hatchling==1.32.4"]
    assert hashlib.sha256((root / "LICENSE").read_bytes()).hexdigest() == (
        "0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0"
    )


def test_direct_dependency_inventory_requires_conscious_review():
    metadata = tomllib.loads((Path(settings.BASE_DIR) / "pyproject.toml").read_text())
    runtime = {_dependency_name(item) for item in metadata["project"]["dependencies"]}
    development = {
        _dependency_name(item) for item in metadata["project"]["optional-dependencies"]["dev"]
    }

    assert runtime == EXPECTED_RUNTIME_DEPENDENCIES
    assert development == EXPECTED_DEV_DEPENDENCIES


def test_license_and_brand_boundaries_are_documented():
    root = Path(settings.BASE_DIR)
    required = {
        "BRAND_POLICY.md",
        "NOTICE.md",
        "THIRD_PARTY_LICENSES.md",
        "licenses/Inter-OFL-1.1.txt",
    }
    assert all((root / path).is_file() for path in required)
    assert "erfasst das\nWerkblatt Brand System nicht" in (root / "BRAND_POLICY.md").read_text()
    assert "SIL OPEN FONT LICENSE Version 1.1" in (root / "licenses/Inter-OFL-1.1.txt").read_text()


def test_source_distribution_has_an_explicit_release_boundary():
    metadata = tomllib.loads((Path(settings.BASE_DIR) / "pyproject.toml").read_text())
    included = set(metadata["tool"]["hatch"]["build"]["targets"]["sdist"]["include"])

    assert {"/src", "/static", "/templates", "/LICENSE", "/BRAND_POLICY.md"} <= included
    assert "/output" not in included
    assert "/var" not in included
    assert "/db.sqlite3" not in included
