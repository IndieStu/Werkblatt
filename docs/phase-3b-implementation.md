# Phase 3b: Implementierungsstand

Status: abgeschlossen; Freigabe-Gate vor Phase 4  
Stand: 28. August 2026

## Umgesetzt

- optionales Organisationsprofil im bestehenden Organisationsmodul
- organisationsbezogene Asset-Bibliothek über die normale Werkblatt-Oberfläche
- sichere SVG- und PNG-Validierung, private Originale und sichere PNG-Vorschauen
- unveränderliche Asset-Versionen mit SHA-256 und bewusstem Versionswechsel
- Organization-Admin-Berechtigung für Asset- und Vorlagenverwaltung
- versionierte, aktivierbare und duplizierbare Dokumentvorlagen
- Inline-Upload aus der Vorlagenverwaltung über denselben Asset-Service
- Logo-Rolle, Dokumentzone, Reihenfolge und optionale Beschriftung „Gefördert durch“
- `include_participant_names` ausschließlich pro Dokumentausgabe
- Abschlussdokument, druckbare Teilnahmeliste und vorbereitete anonymisierte Ausgabe
- sieben kontrollierte Custom-Field-Typen; aggregierte Geschlechtsangaben bleiben Custom Fields
- frühzeitige Workshopzuordnung und dynamische Zusatzfelder im Dokumentationsentwurf
- vollständiges Einfrieren von Vorlagenstand, Ausgaben, Asset-Versionen und Custom Fields im Revisions-Snapshot
- getrennte, idempotente PDF-Erzeugung mit eigenem Status und Hash
- WeasyPrint als primärer Renderer, klar ausgewiesener ReportLab-Fallback
- private tenantgeprüfte PDF-Downloads
- optionaler WebDAV-Upload ohne offene Finalisierungstransaktion und wiederholbarer Fehlerstatus
- Management-Command `retry_document_storage` für fehlgeschlagene externe Speicherung
- persistentes privates Medien-Volume im Compose-Setup

## Sicherheitsgrenzen

Asset-Originale werden nicht über öffentliche Media-URLs ausgeliefert. Preview-, Download-, Auswahl- und Zuordnungszugriffe sind tenantgebunden. SVGs mit Scripts, Event-Handlern, `foreignObject`, DTDs, Entities, externen oder aktiven Referenzen werden abgewiesen. Storage-Keys werden ausschließlich serverseitig erzeugt.

Die fachliche Finalisierung erzeugt weiterhin ausschließlich den lokalen unveränderlichen Snapshot. PDF-Rendering und WebDAV laufen danach ohne lang laufende Datenbanktransaktion und können unabhängig wiederholt werden.

## QA-Ergebnis

- vollständige Python-Test-Suite: 31 Tests bestanden
- Ruff-Lint und Formatprüfung bestanden
- Django-Systemcheck bestanden
- Django-Deployment-Check nur mit erwarteter Warnung zum absichtlich unsicheren lokalen Test-Secret; produktiv wird `DJANGO_SECRET_KEY` als Secret gesetzt
- Migration-Check ohne ausstehende Änderungen
- Abschlussdokument und Teilnahmeliste als echte A4-PDFs erzeugt, erneut gerendert und visuell geprüft
- Asset-Bibliothek und Vorlagenverwaltung im Desktop-Browser geprüft
- responsive Vorlagenansicht bei 390 x 844 Pixeln ohne horizontalen Überlauf geprüft
- keine Browser-Konsolenfehler

Die lokale macOS-Laufzeit enthält keine Pango-Systembibliothek. Deshalb wurde bei der lokalen visuellen QA der dokumentierte ReportLab-Fallback verwendet. Der Produktionscontainer installiert die für WeasyPrint notwendigen Pango-/GDK-Bibliotheken; ein Containerlauf war lokal mangels Docker-Binary nicht möglich.

## Noch nicht Teil von Phase 3b

- produktive Authentik-, Pretix- und WebDAV-Credentials
- produktiver Container-/VPS-Rollout
- native Workshop-Erfassungsoberfläche
- freie Layoutgestaltung, digitale Unterschriften oder Scanablage

Phase 4 wurde nicht begonnen.
