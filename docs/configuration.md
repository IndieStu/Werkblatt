# Konfiguration

Ausgangspunkt ist `.env.example`. Produktive `.env`-Dateien und Secrets werden niemals committet. Deployment-Plattformen sollen Secrets als geschützte Dateien bereitstellen, die über `*_FILE` eingelesen werden. Direkter Wert und zugehöriger `*_FILE`-Wert dürfen nie gleichzeitig gesetzt sein. Ausgaben aufgelöster Produktionskonfiguration dürfen keine Secret-Werte protokollieren.

## Organisationskontext im Pilotbetrieb

`DEFAULT_ORGANIZATION_SLUG` wählt derzeit ausschließlich für eine Single-Tenant-Pilotinstallation mit genau einer Organisation den Organisationskontext. Diese Einstellung ist keine Multi-Tenant-Routingstrategie. Vor Aufnahme einer zweiten Organisation muss die aktive Organisation membershipbasiert bestimmt und bei mehreren Memberships über eine serverseitig validierte Auswahl mit sicherem Session-Kontext gewechselt werden. Der geplante Hosted-Betrieb teilt eine Django-/PostgreSQL-Instanz zwischen strikt isolierten Organisationen; eine Instanz pro Organisation wird nicht vorausgesetzt. Separate Installationen bleiben für Self-Hosting und besondere Isolationsanforderungen möglich.

## Öffentliche URL

`WERKBLATT_PUBLIC_BASE_URL`, `DJANGO_ALLOWED_HOSTS` und `DJANGO_CSRF_TRUSTED_ORIGINS` werden auf die öffentliche URL der jeweiligen Installation gesetzt. Lokal wird üblicherweise `http://localhost:8000` verwendet.

TLS wird durch den vorgeschalteten Reverse Proxy terminiert. Die Anwendung aktiviert zusätzlich HTTPS-Redirect und einjähriges HSTS außerhalb des Debug-Modus. `includeSubDomains` und Browser-Preload bleiben bewusste Entscheidungen des jeweiligen Betreibers.

## Projekt- und Hostingangaben

`WERKBLATT_SOFTWARE_AUTHOR_LABEL` und `WERKBLATT_SOFTWARE_AUTHOR_URL` bezeichnen
den Ursprung des Open-Source-Projekts; standardmäßig ist dies Timo Hecken.
`WERKBLATT_SOFTWARE_COLLABORATION_LABEL` und
`WERKBLATT_SOFTWARE_COLLABORATION_URL` nennen Zircula e.V. dauerhaft als engen
Kooperationspartner. Diese Angaben sind von der konkreten Betreiberorganisation
unabhängig.
`WERKBLATT_HOSTING_PROVIDER_LABEL` ist eine optionale deploymentspezifische
Footerangabe, beispielsweise „In collaboration with and hosted by Example
Organization“. Sie behauptet keine Urheberschaft und bleibt bei klassischen
Self-Hosting-Installationen standardmäßig leer.

Die optional überschreibbaren Angaben `WERKBLATT_SOFTWARE_REPOSITORY_URL`,
`WERKBLATT_USER_DOCUMENTATION_URL` und `WERKBLATT_ISSUE_TRACKER_URL` versorgen
den Bereich „Hilfe & Projekt“ in den persönlichen Einstellungen. Standardmäßig
verweisen sie auf das öffentliche Werkblatt-Repository, seine Nutzungsanleitung
und den Issue-Tracker.

## Authentik / OIDC

Die Anwendung ist für einen eigenen Authentik OAuth2/OIDC-Provider mit Application-Slug `werkblatt` vorbereitet:

- Flow: Authorization Code mit PKCE;
- Redirect URI: `<PUBLIC_BASE_URL>/auth/oidc/callback/`;
- eigener Issuer je Application-Slug;
- Subject: stabile Authentik-UUID;
- Scopes: `openid email profile groups`;
- Gruppen/Entitlements: `Werkblatt Admins`, `Werkblatt Editors` und `Werkblatt Users`;
- Rollen: Admin-Gruppe -> `Organization Admin`, Editor-Gruppe -> `Editor`, sonst
  freigegebene Gruppe -> `Workshop User`. Bei mehreren Gruppen hat Admin vor
  Editor Vorrang.

Client-ID und Client-Secret werden durch den jeweiligen Betreiber erzeugt. Das Secret kann über `OIDC_CLIENT_SECRET_FILE` eingelesen werden. Werkblatt verwendet keine Authentik-Admin-API.

`OIDC_ISSUER` enthält zusätzlich den exakt erwarteten Issuer aus Authentik. Werkblatt akzeptiert Identitäten ausschließlich über `(issuer, sub)`; eine E-Mail-Adresse ist kein Identitätsschlüssel.

## Pretix

Der kanonische Standard-Ursprung ist `https://pretix.eu`; `PRETIX_ORGANIZER` enthält den Organizer-Slug der jeweiligen Installation. Die umleitende Variante `https://www.pretix.eu` wird bewusst nicht verwendet, da Werkblatt Redirects ablehnt und den API-Token nicht an ein Redirectziel weiterreicht.

Ein dedizierter Team-API-Token soll nur lesenden Zugriff auf Organizer, Events, Subevents und für die Teilnehmerübernahme notwendige Orders/Positions erhalten. Er wird ausschließlich über `PRETIX_API_TOKEN_FILE` eingelesen und weder in Chat noch Git geschrieben.

Phase 1 verwendet synthetische API-Fixtures. Reale Event-IDs sind erst für den integrierten Provider-Test erforderlich.

Nach lokaler Secret-Konfiguration wird der Import bewusst manuell ausgelöst:

```bash
python manage.py sync_pretix --workshop-reference SYNTHETIC-TEST-EVENT --include-test-events
```

Die HTTP-Abfragen laufen vor der kurzen Datenbanktransaktion. Ein langsames oder nicht erreichbares Pretix hält daher keine lang laufende DB-Transaktion offen.

## Private Dateien und WebDAV

Logo-Originale, sichere PNG-Vorschauen und erzeugte PDFs liegen im privaten Medienverzeichnis. Dieses Verzeichnis muss im Deployment persistent und privat eingebunden werden; es darf nicht direkt vom Webserver veröffentlicht werden. Downloads und Vorschauen laufen über tenantgeprüfte Django-Endpunkte.

Ohne `WEBDAV_BASE_URL` verbleiben PDFs ausschließlich im privaten lokalen Volume. Für die optionale Ablage in Nextcloud/WebDAV werden zusätzlich `WEBDAV_USERNAME`, `WEBDAV_PASSWORD` und `WEBDAV_ROOT` gesetzt. Externe Aufrufe erfolgen erst nach der fachlichen Finalisierung und ohne offene Datenbanktransaktion. Fehlgeschlagene Uploads lassen sich wiederholen mit:

```bash
python manage.py retry_document_storage
```

`WEBDAV_TRUST_MODE=hosted` lehnt interne, Loopback- und Link-Local-Ziele ab. Einzelne administrativ kontrollierte Hosts können über `WEBDAV_ALLOWED_HOSTS` freigegeben werden. `self_hosted` erlaubt bewusst interne HTTPS-Ziele für selbst betriebene Nextcloud-Installationen; damit übernimmt der Betreiber die Netzvertrauensgrenze. Redirects bleiben in beiden Modi deaktiviert, URL-Credentials sind verboten und Secrets werden weder in Datensätzen noch Fehlermeldungen gespeichert.

## Produktionsmodus und Lockfile

Bei `DJANGO_DEBUG=false` startet Werkblatt nicht mit leerem, `CHANGE_ME` oder dem Development-Secret. `DJANGO_SECRET_KEY_FILE`, `POSTGRES_PASSWORD_FILE`, `OIDC_CLIENT_SECRET_FILE`, `PRETIX_API_TOKEN_FILE` und `WEBDAV_PASSWORD_FILE` können auf geschützte Secret-Dateien der jeweiligen Deployment-Plattform zeigen. Direkte Variablen bleiben für lokale Entwicklung und CI möglich. Die Abhängigkeiten werden mit uv 0.8.15 in `uv.lock` inklusive Artefakt-Hashes festgehalten. Entwicklung, CI und Container verwenden `uv sync --frozen`; Updates erfolgen bewusst über `uv lock --upgrade-package <paket>` mit anschließendem Test- und Vulnerability-Gate.
