# Werkblatt

**Werkblatt is an open-source application for documenting workshops, attendance and project-related reporting.**

Werkblatt ist als selbst hostbare, mandantenfähige Anwendung konzipiert. Anmeldung und Workshopquelle sind über OIDC beziehungsweise Pretix integrierbar; die internen Fachmodelle bleiben davon unabhängig.

Das unabhängige Open-Source-Projekt wurde von Timo Hecken initiiert und wird von
ihm gepflegt. Zircula e.V. ist Erstanwender und enger Entwicklungspartner.

Aktueller Stand: technischer Pilot nach Phase 4a. Noch kein öffentlicher produktiver Release.

## Entwicklung

Produktionsziel ist Python 3.13; für die lokale Entwicklung und CI wird auch Python 3.12 unterstützt. Abhängigkeiten sind mit uv reproduzierbar gelockt. Alternativ kann Docker Compose verwendet werden.

```bash
uv sync --frozen --all-extras
export DJANGO_DEBUG=true
uv run python manage.py migrate
uv run python manage.py bootstrap_organization --name "Example Organization"
uv run python manage.py runserver
```

Die vollständige Phase-0-Entscheidung steht unter [`docs/phase-0-architektur.md`](docs/phase-0-architektur.md). Konfiguration und Secrets werden in [`docs/configuration.md`](docs/configuration.md) beschrieben. Die feste fachliche Rollen- und Berechtigungsmatrix steht unter [`docs/roles.md`](docs/roles.md).

## Status der Funktionen

- vorhanden: tenantgebundene Organisationen, User-/Identity-Modell, Rollen, OIDC, Pretix-Adapter mit sicherem Importstichtag und Veranstaltungsregeln, filterbare Workshopliste, Web-Branding, Dokumentationsrevisionen, versionierte Asset-Bibliothek, wiederverwendbare und sicher archivierbare Dokumentvorlagen, Custom Fields, Abschluss-PDFs, druckbare Teilnahmelisten, optionaler WebDAV-Storage sowie organisationsbezogene aggregierte Statistik mit CSV-Export;
- noch nicht vorhanden: lokale Accounts, Hosted-Multi-Tenant-Auswahl und öffentlicher Release.

## Lizenz

Der Werkblatt-Programmcode steht unter der **GNU Affero General Public License
Version 3 oder jeder späteren Version** (`AGPL-3.0-or-later`). Der vollständige
Lizenztext steht in [`LICENSE`](LICENSE).

Das Werkblatt Brand System ist ausdrücklich nicht Bestandteil dieser
Lizenzfreigabe. Name, Logos, Signet, Claim-Lockups, Icons, Brand-Tokens und
Login-Hintergrund bleiben vorbehalten. Die verbindliche Abgrenzung und die
betroffenen Pfade stehen in [`BRAND_POLICY.md`](BRAND_POLICY.md).

Inter und weitere Drittkomponenten bleiben unter ihren jeweiligen Lizenzen.
Eine Übersicht steht in [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md),
die Projekt- und Rechtezuordnung in [`NOTICE.md`](NOTICE.md).

Die dokumentierte Entscheidung und das technische Kompatibilitätsaudit stehen
in [`docs/licensing.md`](docs/licensing.md). Beiträge folgen
[`CONTRIBUTING.md`](CONTRIBUTING.md) und werden unter derselben Lizenz mit DCO
Sign-off eingereicht.
