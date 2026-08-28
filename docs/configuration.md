# Konfiguration

Ausgangspunkt ist `.env.example`. Produktive `.env`-Dateien und Secrets werden niemals committet; auf dem Host erhalten sie Modus 600. `docker compose config` wird nur mit `--quiet` verwendet, damit interpolierte Werte nicht in Ausgaben gelangen.

## Öffentliche URL

Für den Zircula-Pilot ist `https://werkblatt.zircula.org` vorgesehen. Lokal wird `http://localhost:8000` verwendet.

TLS und der allgemeine HSTS-Header werden wie bei den übrigen Zircula-Diensten durch Caddy erzwungen. Die Anwendung aktiviert zusätzlich HTTPS-Redirect und einjähriges HSTS außerhalb des Debug-Modus. `includeSubDomains` und Browser-Preload bleiben entsprechend der bestehenden Infrastruktur-Governance bewusste, zentrale Entscheidungen.

## Authentik / OIDC

Die Anwendung ist für einen eigenen Authentik OAuth2/OIDC-Provider mit Application-Slug `werkblatt` vorbereitet:

- Flow: Authorization Code mit PKCE;
- Redirect URI: `https://werkblatt.zircula.org/auth/oidc/callback/`;
- eigener Issuer je Application-Slug;
- Subject: stabile Authentik-UUID;
- Scopes: `openid email profile groups`;
- Gruppen/Entitlements: `Werkblatt Admins` und `Werkblatt Users`;
- Rollen: Admin-Gruppe -> `Organization Admin`, sonst freigegebene Gruppe -> `Workshop User`.

Client-ID und Client-Secret werden erst für den integrierten Test erzeugt. Das Secret wird ausschließlich als `OIDC_CLIENT_SECRET` auf dem Host gesetzt. Werkblatt verwendet keine Authentik-Admin-API.

`OIDC_ISSUER` enthält zusätzlich den exakt erwarteten Issuer aus Authentik. Werkblatt akzeptiert Identitäten ausschließlich über `(issuer, sub)`; eine E-Mail-Adresse ist kein Identitätsschlüssel.

## Pretix

Der vorbereitete Ursprung ist `https://www.pretix.eu`, Organizer `WERK`. Groß-/Kleinschreibung des tatsächlichen Organizer-Slugs wird vor dem ersten Live-Test bestätigt.

Ein dedizierter Team-API-Token soll nur lesenden Zugriff auf Organizer, Events, Subevents und für die Teilnehmerübernahme notwendige Orders/Positions erhalten. Er wird ausschließlich als `PRETIX_API_TOKEN` gesetzt und weder in Chat noch Git geschrieben.

Phase 1 verwendet synthetische API-Fixtures. Reale Event-IDs sind erst für den integrierten Provider-Test erforderlich.

Nach lokaler Secret-Konfiguration wird der Import bewusst manuell ausgelöst:

```bash
python manage.py sync_pretix
```

Die HTTP-Abfragen laufen vor der kurzen Datenbanktransaktion. Ein langsames oder nicht erreichbares Pretix hält daher keine lang laufende DB-Transaktion offen.

## Private Dateien und WebDAV

Logo-Originale, sichere PNG-Vorschauen und erzeugte PDFs liegen im privaten Medienverzeichnis. Im Compose-Betrieb wird dieses Verzeichnis über das Volume `werkblatt-media` persistent eingebunden und nicht direkt vom Webserver veröffentlicht. Downloads und Vorschauen laufen über tenantgeprüfte Django-Endpunkte.

Ohne `WEBDAV_BASE_URL` verbleiben PDFs ausschließlich im privaten lokalen Volume. Für die optionale Ablage in Nextcloud/WebDAV werden zusätzlich `WEBDAV_USERNAME`, `WEBDAV_PASSWORD` und `WEBDAV_ROOT` gesetzt. Externe Aufrufe erfolgen erst nach der fachlichen Finalisierung und ohne offene Datenbanktransaktion. Fehlgeschlagene Uploads lassen sich wiederholen mit:

```bash
python manage.py retry_document_storage
```

`WEBDAV_TRUST_MODE=hosted` lehnt interne, Loopback- und Link-Local-Ziele ab. Einzelne administrativ kontrollierte Hosts können über `WEBDAV_ALLOWED_HOSTS` freigegeben werden. `self_hosted` erlaubt bewusst interne HTTPS-Ziele für selbst betriebene Nextcloud-Installationen; damit übernimmt der Betreiber die Netzvertrauensgrenze. Redirects bleiben in beiden Modi deaktiviert, URL-Credentials sind verboten und Secrets werden weder in Datensätzen noch Fehlermeldungen gespeichert.

## Produktionsmodus und Lockfile

Bei `DJANGO_DEBUG=false` startet Werkblatt nicht mit leerem, `CHANGE_ME` oder dem Development-Secret. `DJANGO_SECRET_KEY` muss als starkes Environment Secret gesetzt sein. Die Abhängigkeiten werden mit uv 0.8.15 in `uv.lock` inklusive Artefakt-Hashes festgehalten. Entwicklung, CI und Container verwenden `uv sync --frozen`; Updates erfolgen bewusst über `uv lock --upgrade-package <paket>` mit anschließendem Test- und Vulnerability-Gate.
