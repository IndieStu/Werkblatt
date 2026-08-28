# Phase 4a: Production-/VPS-Preflight

Stand: 2026-08-28. Dieser Bericht beschreibt den geprüften Zwischenstand und ist ausdrücklich keine Freigabe für Phase 4b.

## 1. Geprüfter Commit

Ausgangspunkt der Phase 4a ist Werkblatt-Commit `4c1da245a0c16d97759174468ad6e78743e27495`. Die Phase-4a-Änderungen erhalten nach vollständigem lokalen und CI-Gate einen eigenen Commit; dessen Hash wird hier und im Übergabebericht ergänzt. Referenzstände: Infrastruktur-Checkout auf dem VPS `514c1e0f`, Remote-Infrastruktur `ab7654`, Zircula-Automation `972f8d` und IntraVox `2e474d`.

## 2. Zielarchitektur auf dem VPS

Vorhandenes Zielsystem: Ubuntu 26.04 LTS, Docker 29.7.2, Compose 5.5.0, 8 vCPU und 15 GiB RAM. Werkblatt erhält einen eigenen App- und PostgreSQL-17-Container ohne veröffentlichten Host-Port. Nur Caddy erreicht den Webcontainer über `zircula_frontend`; App und Datenbank kommunizieren im isolierten Netz `werkblatt_internal`. Medien und Datenbank liegen als Bind-Mounts unter `/srv/zircula/werkblatt`. Es wird kein paralleler Proxy und keine generische Infrastrukturschicht eingeführt.

## 3. Container-, Volume- und Netzwerkressourcen

Der Webcontainer erhält 2 CPU, 1536 MiB RAM, 256 MiB tmpfs und PID-Limit 256; PostgreSQL 1 CPU, 1024 MiB RAM, 256 MiB Shared Memory und PID-Limit 256. Root-Dateisysteme sind read-only, Capabilities entfernt. Der VPS hatte im Preflight rund 9 GiB verfügbaren RAM, 205 GiB freien Plattenplatz und keinen Swap. Dauerhaft benötigt Werkblatt `/srv/zircula/werkblatt/media`, `/srv/zircula/werkblatt/postgres` und `/srv/zircula/werkblatt/secrets`.

## 4. Reverse-Proxy-, DNS- und TLS-Anforderungen

`werkblatt.zircula.org` zeigt derzeit auf `217.11.48.193` beziehungsweise `2a00:1828:3000::1:2f3:2`, nicht auf den Zircula-VPS. Zielwerte sind A `195.90.217.88` und AAAA `2a00:6800:3:1128::1`. Das bestehende Caddy-Setup ist valide und veröffentlicht nur 80/443; der neue Host erhält die vorhandenen zentralen Security-Header und `reverse_proxy werkblatt:8000`. TLS darf erst nach DNS-Umschaltung und erfolgreicher Caddy-Zertifikatsausstellung abgenommen werden.

## 5. Authentik-Konfiguration

Authentik 2026.5.6 läuft gesund. Es existieren noch kein Werkblatt-Provider und keine Werkblatt-Gruppen. Benötigt werden die Application `werkblatt`, ein eigener confidential OIDC-Provider mit Authorization Code und PKCE S256, Redirect `https://werkblatt.zircula.org/auth/oidc/callback/`, Scopes `openid email profile groups` sowie ausschließlich `Werkblatt Users` und `Werkblatt Admins` im Gruppenclaim. Das Secret wird direkt als Host-Secret gespeichert und nie ausgegeben. Einrichtung und die drei Loginfälle (User, Admin, unberechtigt) sind noch offen.

## 6. Pretix-Konfiguration

Ziel ist `https://www.pretix.eu`, Organizer `WERK`. Werkblatt benötigt einen eigenen read-only API-Token; ein möglicherweise in IntraVox vorhandenes Credential wird nicht wiederverwendet oder ausgelesen. Der Synchronisierer importiert Workshops und aktive Registrierungen. Pretix-Testevents sind standardmäßig ausgeschlossen und nur mit expliziter Workshop-Referenz plus `--include-test-events` zulässig. Für den realen Test fehlen noch dedizierter Token und eine vollständig synthetische Testveranstaltung.

## 7. WebDAV-/Nextcloud-Konfiguration

Nextcloud 34.0.3 ist erreichbar. Benötigt werden ein technischer Werkblatt-Benutzer, ein App-Passwort und ein ausschließlich für Werkblatt freigegebener Zielordner. Passwort und Serverantworten werden nicht protokolliert. Finalisierung bleibt lokal atomar; Render-/Storage-Status sind getrennt und ein fehlgeschlagener Upload wird ohne erneute fachliche Finalisierung wiederholt. Technischer Account, Ordner und realer Schreib-/Lese-/Retry-Test sind noch offen.

## 8. Secret-Handling

Git und `.env` enthalten keine produktiven Secrets. `compose.vps.yaml` mountet einzelne Dateien aus `/srv/zircula/werkblatt/secrets` nach `/run/secrets`; Django unterstützt dafür `*_FILE`. Gleichzeitig gesetzter Direkt- und Dateiwert wird abgewiesen. Verzeichnisrechte: 700; Dateien: 600; Eigentümer passend zur Deployment-Gruppe, Containerzugriff read-only. Docker-Config-Prüfungen erfolgen ausschließlich mit `--quiet`. Logs, Chat und Bericht enthalten keine Credential-Werte.

## 9. Backup-/Restore-Ergebnis

Der vorhandene tägliche Backup-Timer war aktiv und der letzte geprüfte Lauf am 2026-08-28 erfolgreich. Er sichert `/srv/zircula`, Infrastruktur und Staging verschlüsselt mit Restic und repliziert auf ein getrenntes System. Für den isolierten Werkblatt-PostgreSQL-Container wird der Backup-Lauf um einen eigenen logischen Dump erweitert; rohe Datenbankdateien allein sind keine ausreichende Sicherung. Der Anwendungstest bildet den vollständigen synthetischen Daten-/Dateigraphen nach. Ein tatsächlicher isolierter VPS-Restore ist vor Phase 4b zwingend.

## 10. Monitoring-/Healthcheck-Konzept

`/health/` prüft den Prozess ohne DB; `/ready/` prüft PostgreSQL. Docker verwendet Readiness, der bestehende Blackbox-Exporter soll die öffentliche Liveness-URL prüfen. Containerlogs rotieren bei 10 MiB mit fünf Dateien; Gunicorn-Accesslogs sind deaktiviert. Alarmiert werden Ausfall, Restart-Schleife, Ressourcen-/Plattenengpass, Backupfehler und aggregierte PDF-/Storage-Fehler. PII, Dokumentinhalte, Tokens und vollständige Remote-Pfade bleiben ausgeschlossen.

## 11. Migrations- und Rollbackplan

Vor Update werden Image-Digest, Werkblatt-Custom-Dump und gemeinsam datierter Medien-Checkpoint festgehalten. Migrationen laufen einmalig mit exakt dem neuen Image vor dem Web-Rollout. Danach folgt Readiness und synthetischer Smoke-Test. Containerrollback verwendet den vorherigen Digest; nach nicht rückwärtskompatibler Migration werden Datenbank und Medien gemeinsam aus dem Pre-Update-Checkpoint wiederhergestellt. Details stehen in `docs/operations/vps-deployment.md`.

## 12. Synthetischer End-to-End-Test

Lokal sind Django-Fach-, Security-, PDF- und Storage-Flows mit synthetischen Daten abgedeckt. Der reale Zielumgebungsweg Login → Workshop → Teilnehmende → Vorlage → Dokumentation → Finalisierung → WeasyPrint-PDF → WebDAV → Download ist noch **nicht vollständig ausführbar**: DNS zeigt auf das falsche System, der Authentik-Provider fehlt, und dedizierte Pretix-/Nextcloud-Credentials fehlen. Dieses Ergebnis darf nicht durch Mocks als erfolgreicher Produktions-E2E umgedeutet werden.

## 13. Verbleibende Risiken

- DNS/TLS und realer OIDC-Flow sind noch ungeprüft.
- Pretix-API-Shape und Berechtigungen müssen mit einem synthetischen Testevent real bestätigt werden.
- WebDAV-Rechte, Quota, Dateinamen und Retry müssen real bestätigt werden.
- Kein tatsächlicher Werkblatt-Restore auf dem VPS, bevor erstmals Werkblatt-Daten gesichert wurden.
- Der VPS besitzt keinen Swap; WeasyPrint-Spitzen und paralleler Backup-Lauf müssen beobachtet werden.
- Die Lizenzentscheidung (AGPL-3.0-or-later) ist noch nicht endgültig abgeschlossen.

## 14. Exakte Schritte für Phase 4b

Phase 4b bleibt gesperrt. Vor einer Freigabe müssen in Phase 4a noch folgende Punkte erfolgreich abgeschlossen und im finalen Bericht nachgetragen werden:

1. DNS A/AAAA kontrolliert auf den Zircula-VPS umstellen und TLS/Header extern prüfen.
2. Unmittelbar zuvor Authentik-Backup verifizieren; Werkblatt-Provider und Gruppen additiv anlegen, Secret direkt auf dem Host speichern und User/Admin/Ablehnung testen.
3. Dedizierten Pretix-read-only-Token direkt als Host-Secret speichern; explizites synthetisches Testevent importieren.
4. Technischen Nextcloud-Benutzer, App-Passwort und Zielordner anlegen; Secret direkt auf dem Host speichern.
5. Geprüftes Image auf den VPS übertragen, isolierte Werkblatt-Datenbank und Medienpfad anlegen, Migrationen ausführen und vollständigen synthetischen E2E durchführen.
6. Werkblatt-Backup erzeugen, in eine isolierte temporäre DB/Medienstruktur zurückspielen und Hash-/Abrufprüfung dokumentieren.
7. Erst danach neuen Phase-4a-Bericht mit allen Ergebnissen vorlegen und erneut ausdrücklich auf die Freigabe für Phase 4b warten.
