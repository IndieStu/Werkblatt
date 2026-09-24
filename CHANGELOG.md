# Changelog

Alle wesentlichen Änderungen an Werkblatt werden in dieser Datei dokumentiert.
Das Projekt verwendet für Tags Semantic Versioning und für das Python-Paket die
entsprechende PEP-440-Schreibweise.

## 0.1.0rc1 – 2026-09-24

Erster formal versionierter Release Candidate für einen kontrollierten,
selbst gehosteten Single-Tenant-Pilotbetrieb.

### Hinzugefügt

- OIDC-Anmeldung mit organisationsgebundenen Rollen Workshop User, Editor und
  Organization Admin;
- Pretix-Import mit Stichtag, Reihenregeln, bestätigten Anmeldungen und
  reversibler Kennzeichnung abgesagter Workshops;
- native Workshopanlage und -bearbeitung;
- filterbare Workshopliste und responsive Monatskalenderansicht;
- Teilnehmer-, Anwesenheits-, Durchführenden- und Custom-Field-Erfassung;
- unveränderliche Dokumentationsrevisionen und Snapshots;
- versionierte Dokumentvorlagen und organisationsbezogene Asset-Bibliothek;
- Abschlussberichte und druckbare Teilnahmelisten als PDF;
- optionaler, wiederholbarer WebDAV-/Nextcloud-Storage;
- organisationsbezogene Statistik und CSV-Export ohne Klarnamen;
- persönliche Einstellungen für Sprache und Hell/Dunkel/System;
- AGPL-3.0-or-later-Lizenzierung des Programmcodes mit separat vorbehaltenem
  Werkblatt Brand System;
- SBOM-, Vulnerability-, Secret-, Lizenzdrift- und Base-Image-Gates in CI.

### Migration

- `workshops.0004_workshop_lifecycle_status` ergänzt den reversiblen Status
  aktiver beziehungsweise abgesagter Workshops.

### Bekannte Grenzen

- `DEFAULT_ORGANIZATION_SLUG` ist ausschließlich ein temporärer
  Single-Tenant-Pilotmechanismus;
- noch keine sichere Organisationsauswahl für Hosted Multi-Tenancy;
- noch kein öffentlicher, automatisch zurückgesetzter Demo-Modus;
- PDF-Rendering läuft synchron im Webworker;
- Sitzungsentzug nach Entfernung einer OIDC-Gruppe erfolgt noch nicht sofort;
- ein periodischer Pretix-Sync ist Aufgabe der jeweiligen Deploymentplattform.
