# Werkblatt

**Werkblatt is an open-source application for documenting workshops, attendance and project-related reporting.**

Werkblatt entsteht zunächst für den Zircula-Pilot und wird von Anfang an als selbst hostbare, mandantenfähige Anwendung konzipiert. Anmeldung und Workshopquelle sind über OIDC beziehungsweise Pretix integrierbar; die internen Fachmodelle bleiben davon unabhängig.

Aktueller Stand: Phase 2 - Dokumentationsworkflow. Noch kein produktiver Release.

## Entwicklung

Produktionsziel ist Python 3.13; für die lokale Entwicklung und CI wird auch Python 3.12 unterstützt. Alternativ kann Docker Compose verwendet werden.

```bash
python3.13 -m venv .venv
.venv/bin/pip install -e '.[dev]'
export DJANGO_DEBUG=true
.venv/bin/python manage.py migrate
.venv/bin/python manage.py bootstrap_organization --name "Zircula e.V."
.venv/bin/python manage.py runserver
```

Die vollständige Phase-0-Entscheidung steht unter [`docs/phase-0-architektur.md`](docs/phase-0-architektur.md). Konfiguration und Secrets werden in [`docs/configuration.md`](docs/configuration.md) beschrieben.

## Status der Funktionen

- vorhanden: tenantgebundene Organisationen, internes User-/Identity-Modell, Rollen, OIDC-Vorbereitung, Pretix-Adapter, Workshopliste, Werkblatt Web-Branding sowie Entwürfe, Anwesenheit, Walk-ins, Durchführende, Abschluss und unveränderliche Revisionen;
- noch nicht vorhanden: PDF, WebDAV, lokale Accounts und manuelle Workshop-UI.

## Lizenz

AGPL-3.0-or-later wird als bevorzugte Richtung geprüft. Die endgültige Software- und Markenlizenzentscheidung ist noch nicht getroffen; daher liegt noch keine `LICENSE`-Datei bei.
