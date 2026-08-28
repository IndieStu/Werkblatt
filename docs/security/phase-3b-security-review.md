# Security-Review Phase 3b

Basis des Reviews: Commit `c224ddf3105092fbe10ec56cc5e10a78d8fcf203` („Implement document templates and PDF workflow“) auf `IndieStu/Werkblatt`, Branch `main`. Die daraus entstandenen Härtungen wurden bis einschließlich Commit `5afea13bab58b4aaf5917482f2b7250e2891bada` geprüft. Phase 4 ist nicht Bestandteil dieses Reviews.

## Verifiziertes Ergebnis

GitHub Actions [CI-Lauf 11](https://github.com/IndieStu/Werkblatt/actions/runs/33206391080) für Commit `5afea13bab58b4aaf5917482f2b7250e2891bada` ist vollständig erfolgreich. Er umfasst Python 3.12 und 3.13 mit PostgreSQL 17 einschließlich der drei echten Parallelitätstests, Produktions- und Migration-Checks, Dependency-Audit, Secret-Scan, Container-Build, zwei unabhängige reale WeasyPrint-Läufe mit Inhalts-/Metadaten-/Rastervergleich sowie den Trivy-Scan auf ungeklärte kritische Findings. Lokal bestanden 62 Tests; die drei PostgreSQL-spezifischen Parallelitätstests wurden dort erwartungsgemäß übersprungen und in CI erfolgreich ausgeführt.

## Gefundene und behobene Probleme

- Produktionsstart mit bekanntem Development-Secret war möglich: Start wird bei `DEBUG=false` jetzt abgewiesen.
- historische PDFs lasen Workshop- und Erstellerdaten teilweise erneut aus aktuellen Datensätzen: Abschlussmetadaten und Workshopdarstellung kommen jetzt vollständig aus dem unveränderlichen Snapshot.
- SVG-Prüfung war überwiegend blacklistbasiert: strikte Element-/Attribut-Allowlist sowie Node-/Tiefenlimits ergänzt; aktive, externe und datenbasierte Referenzen bleiben verboten.
- PNGs mit Bytes hinter `IEND` sowie Dekompressionsbomben waren nicht explizit abgedeckt: strikte Chunk-Endprüfung, Pixel-/Dimensions-/Dateilimits und Bomb-Erkennung ergänzt.
- Asset-/Vorlagenservices vertrauten ausschließlich auf View-Autorisierung: Organization-Admin-Prüfung als zweite Schicht ergänzt.
- interne Render-Services prüften keine Mitgliedschaft: Tenant-Mitgliedschaft wird nun im Service erzwungen.
- WeasyPrint konnte standardmäßig weitere URLs auflösen: Fetcher akzeptiert ausschließlich die exakt serverseitig bestimmten Asset-/Font-URIs.
- Pretix-Antwortgrößen waren unbegrenzt: Streaming-Limit 5 MiB ergänzt; DNS wird unmittelbar vor jedem Request erneut vollständig als öffentlich geprüft.
- WebDAV hatte kein ausdrückliches SSRF-Trust-Modell: `hosted` und `self_hosted`, HTTPS-/Credential-/Root-Validierung und deaktivierte Redirects ergänzt.
- gleichzeitige PDF-/Storage-Versuche konnten dieselbe Arbeit beginnen: atomare `rendering`-/`storing`-Claims und getrennte Idempotenz-Constraints für Entwurf und Revision ergänzt.
- Abhängigkeiten waren nicht gelockt; der erste Audit fand verwundbare Pillow-, WeasyPrint- und pytest-Versionen: uv-Lockfile eingeführt und auf Pillow 12.3, WeasyPrint 69 sowie pytest 9 aktualisiert; erneuter `pip-audit` ohne bekannte Schwachstelle.
- Runtime-Container war beschränkt, aber nicht read-only vorbereitet: gelockter Build, UID 10001, read-only Root, dediziertes tmpfs, Capability-Drop, No-New-Privileges, Speicher-/PID-Grenzen ergänzt.

## Security-Testmatrix

| Bereich | Automatisierte Absicherung |
| --- | --- |
| Tenant/Rollen | unauthenticated, Workshop User, Organization Admin, Superuser ohne Membership; fremde Asset-, Version-, Template-, Workshop-, Preview-, Download- und Form-IDs |
| Upload | PNG-Signatur/MIME-Abweichung, Korruption, Größen/Pixel, angehängte Bytes, Traversal-Dateinamen; SVG Script/Event/foreignObject/DTD/XXE/HTTP/file/data/CSS/Animation/Case/Komplexität |
| Historie | Snapshot-/Hash-Unveränderlichkeit, Template-/Asset-Version 1 nach späterer Version 2, spätere Workshop-/Erstelleränderung, kanonischer Hash |
| PDF | Django-Escaping adversarialer Berichtswerte, freigegebener URL-Fetcher, tenantgebundenes Rendering/Download, produktiver WeasyPrint-Container mit zwei PDF-Arten, Text-/Seiten-/Rasterprüfung |
| Pretix/WebDAV | Auflösungswechsel, private Ziele, Redirect-Verbot, Response-Limit, Trust-Modi, Credentials nicht in Fehlerstatus/Logs |
| OIDC | Issuer, Audience, Sub, Gruppen, Rollenwechsel und Beschränkung auf konfigurierte Organisation; Authlib übernimmt Signatur, State, Nonce und PKCE S256 |
| Concurrency | Versions-/Finalisierungs-Sperren unter PostgreSQL; atomare PDF-/Storage-Claims und Unique Constraints |
| Restore | synthetischer relationaler Dump/Restore plus historische private Asset- und PDF-Dateien |

## Produktions-Gates

- `ruff check` und `ruff format --check`
- Migration- und Django-Systemcheck
- vollständige Tests plus separat ausgewiesene `security`-Gruppe
- `check --deploy` mit produktionsnahen synthetischen Secrets
- `uv lock --check` und `pip-audit`
- Gitleaks-Secret-Scan
- reproduzierbarer Produktionscontainer
- echter WeasyPrint-Lauf für Abschlussbericht und Teilnahmeliste im Container
- PDF-Text, Seiten, Metadaten, Rasterung und deterministischer Rastervergleich
- Trivy-Scan auf ungeklärte kritische Image-Findings

## Bewusst verbleibende Grenzen

- DNS kann sich theoretisch noch zwischen letzter Auflösung und Socket-Verbindung ändern. Pretix- und Hosted-WebDAV-Ziele sind Deployment-Konfiguration, keine Benutzereingabe; zusätzlich werden Redirects deaktiviert und Auflösungswechsel vor Requests getestet. Ein verbindungsseitiges IP-Pinning mit korrekter TLS-SNI wird nicht als eigener Netzwerkstack implementiert. Vor einem frei konfigurierbaren Hosted-Multi-Tenant-Angebot ist ein Egress-Proxy bzw. Firewall-Allowlisting das nächste Gate.
- Entzug einer Authentik-Gruppe beendet eine bereits laufende Django-Session nicht sofort. Vor Hosted-Multi-Tenant-Betrieb sind kurze Session-Laufzeiten oder Backchannel-Logout/Session-Revocation festzulegen.
- PDF-Rendering läuft synchron im Gunicorn-Worker. Eingabelängen, URL-Allowlist, 30-Sekunden-Worker-Timeout und Containerressourcen begrenzen das Risiko; vor hohem öffentlichen Volumen gehört Rendering in einen separat limitierten Worker.
- HSTS `includeSubDomains` und Preload werden bewusst am Zircula-Reverse-Proxy entschieden. Deshalb meldet `check --deploy` nachvollziehbar W005 und W021; keine Warnung wird mehr unterdrückt.
- GitHub Actions sind auf feste Commit-SHAs gepinnt. Die Python-, PostgreSQL- und uv-Container-Basisimages verwenden weiterhin nachvollziehbare Versionstags statt Plattform-Multiarch-Digests; deren Digest-Pinning und turnusmäßige Renovate-/Dependabot-Aktualisierung ist vor einem formalen Release mit höherem Supply-Chain-Assurance-Level festzulegen.

## Hosted-Multi-Tenant vor Produktivfreigabe

Erforderlich bleiben Egress-Netzregeln, zentrale Session-Revocation, externe Render-Worker-Limits, regelmäßiger realer PostgreSQL-/Volume-Restore, Monitoring/Alerting ohne PII sowie Rotation und Least-Privilege-Prüfung der Authentik-, Pretix- und WebDAV-Credentials.
