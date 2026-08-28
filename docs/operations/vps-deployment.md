# Zircula-VPS: Deployment und Betrieb

Diese Runbook beschreibt den vorgesehenen Pilotbetrieb. Sie autorisiert keine Produktionseinspielung; Phase 4b beginnt ausschließlich nach ausdrücklicher Freigabe.

## Zielbild

Werkblatt läuft als zustandsloser App-Container und eigener PostgreSQL-17-Container aus `compose.vps.yaml`. Nur der Webcontainer ist mit `zircula_frontend` für Caddy verbunden; beide Container teilen das isolierte interne Netz `werkblatt_internal`. Es wird kein Host-Port veröffentlicht. Persistente Dateien liegen unter `/srv/zircula/werkblatt/media` und `/srv/zircula/werkblatt/postgres`. Secrets liegen einzeln unter `/srv/zircula/werkblatt/secrets`.

Der Webcontainer läuft als UID/GID 10001, mit schreibgeschütztem Root-Dateisystem, ohne Linux-Capabilities, mit `no-new-privileges`, 2 CPU, 1536 MiB RAM, 256 MiB temporärem Speicher und maximal 256 Prozessen. PostgreSQL erhält 1 CPU, 1024 MiB RAM, 256 MiB Shared Memory und maximal 256 Prozesse. JSON-Logs rotieren bei 10 MiB mit fünf Dateien. Gunicorn schreibt Fehler, aber keine personenbezogenen Access-Logs.

## Reverse Proxy und DNS

Vor Deployment müssen A und AAAA von `werkblatt.zircula.org` auf den tatsächlichen VPS zeigen: `195.90.217.88` und `2a00:6800:3:1128::1`. Aktuell (Preflight 2026-08-28) zeigen beide Einträge auf ein anderes System; deshalb darf Caddy noch kein öffentliches Werkblatt-Zertifikat als gegeben voraussetzen.

Nach DNS-Umstellung wird in der vorhandenen Caddy-Konfiguration ausschließlich dieser Host ergänzt:

```caddyfile
werkblatt.zircula.org {
    import security_headers
    reverse_proxy werkblatt:8000
}
```

Anschließend zuerst `caddy validate`, dann Reload, Zertifikatsausstellung und externe Prüfung von HTTPS, Redirects und Security-Headern. Werkblatt vertraut `X-Forwarded-Proto` nur über den kontrollierten Proxy. Ein direkter öffentlicher App-Port bleibt verboten.

## Geordnete Aktualisierung

1. Geprüften Git-Commit und unveränderlichen Image-Digest festhalten; vorherigen Digest bewahren.
2. Letzten zentralen Backup-Lauf prüfen und zusätzlich Werkblatt-Custom-Dump plus datierten Medien-Checkpoint erzeugen.
3. Neues Image bauen, signieren beziehungsweise Digest dokumentieren und lokal auf kritische Schwachstellen prüfen.
4. `docker compose -f compose.vps.yaml config --quiet` und Dateirechte prüfen.
5. Einmaligen Migrationscontainer mit demselben Image und denselben Secrets ausführen: `python manage.py migrate --noinput`.
6. Web-Container ersetzen, Readiness abwarten, externen synthetischen Smoke-Test ausführen.
7. Bei Fehlern Container auf den vorherigen Digest zurücksetzen. Nach Datenmigration Datenbank und Medien gemeinsam aus dem Pre-Update-Checkpoint wiederherstellen.

Migration und Webstart werden bewusst getrennt. Es gibt keine Migration beim Start jedes Web-Containers und keine lang laufende Datenbanktransaktion während Pretix- oder WebDAV-Aufrufen.

## Healthchecks und Monitoring

`/health/` ist eine reine Liveness-Prüfung ohne Datenbankzugriff. `/ready/` prüft mit `SELECT 1` die Datenbank. Beide liefern nur Status und `Cache-Control: no-store`, niemals PII oder Konfigurationsdetails. Docker prüft intern `/ready/`; der vorhandene Blackbox-Exporter soll extern `https://werkblatt.zircula.org/health/` prüfen. Alarme: Endpoint-Ausfall, Container-Unhealthy/Restart-Schleife, Speicher über 80 %, Datenträger über 80 %, Backupfehler sowie wiederholte PDF-/Storage-Fehler als aggregierte Zähler. Namen, E-Mail-Adressen, Tokens, Dokumentinhalte und vollständige Remote-Pfade gehören nicht in Logs oder Monitoring-Labels.

## Integrationsabnahme

- Authentik: eigener confidential Provider, Authorization Code + PKCE S256, exakte Redirect-URI und ausschließlich Werkblatt-Gruppenclaims.
- Pretix: eigener read-only Token für Organizer `WERK`; Testmode-Events werden nur mit expliziter `--workshop-reference` und `--include-test-events` importiert.
- Nextcloud: eigener technischer Benutzer mit App-Passwort und nur einem dedizierten Werkblatt-Zielordner; `WEBDAV_BASE_URL`, Benutzer und Root sind nicht geheim, das Passwort liegt als Secret-Datei vor.
- E2E-Daten sind vollständig synthetisch und eindeutig als Test markiert. Nach Abnahme werden Testdokument und Testteilnehmende aus den Zielsystemen nach dem vereinbarten Verfahren entfernt, ohne produktive Datensätze zu berühren.
