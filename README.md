# Werkblatt

**Werkblatt is an open-source application for documenting workshops, attendance and project-related reporting.**

Werkblatt entsteht zunächst für den Zircula-Pilot und wird von Anfang an als selbst hostbare, mandantenfähige Anwendung konzipiert. Anmeldung und Workshopquelle sind über OIDC beziehungsweise Pretix integrierbar; die internen Fachmodelle bleiben davon unabhängig.

Aktueller Stand: Phase 3b - Dokumentvorlagen und PDF-Ausgaben. Noch kein produktiver Release.

## Entwicklung

Produktionsziel ist Python 3.13; für die lokale Entwicklung und CI wird auch Python 3.12 unterstützt. Abhängigkeiten sind mit uv reproduzierbar gelockt. Alternativ kann Docker Compose verwendet werden.

```bash
uv sync --frozen --all-extras
export DJANGO_DEBUG=true
uv run python manage.py migrate
uv run python manage.py bootstrap_organization --name "Zircula e.V."
uv run python manage.py runserver
```

Die vollständige Phase-0-Entscheidung steht unter [`docs/phase-0-architektur.md`](docs/phase-0-architektur.md). Konfiguration und Secrets werden in [`docs/configuration.md`](docs/configuration.md) beschrieben.

## Status der Funktionen

- vorhanden: tenantgebundene Organisationen, User-/Identity-Modell, Rollen, OIDC-Vorbereitung, Pretix-Adapter, Workshopliste, Web-Branding, Dokumentationsrevisionen, versionierte Asset-Bibliothek, wiederverwendbare Dokumentvorlagen, Custom Fields, Abschluss-PDFs, druckbare Teilnahmelisten und optionaler WebDAV-Storage;
- noch nicht vorhanden: lokale Accounts, manuelle Workshop-UI und produktiver Rollout.

## Lizenz

AGPL-3.0-or-later wird als bevorzugte Richtung geprüft. Die endgültige Software- und Markenlizenzentscheidung ist noch nicht getroffen; daher liegt noch keine `LICENSE`-Datei bei.
