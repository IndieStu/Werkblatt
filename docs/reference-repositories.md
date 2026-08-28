# Analysierte Referenz-Repositories

Für Phase 1 wurden am 28. August 2026 folgende Repositories read-only analysiert:

- `zircula-ev/infrastructure`, `main`, Ausgangscommit `ab7654e5ce8d5c3fc24ebac52d738610b6721338`
- `zircula-ev/Zircula-Automation`, `main`, Ausgangscommit `972f8df2b6a1507956eb8e6295b1b36805d982db`
- `IndieStu/IntraVox`, `main`, Ausgangscommit `2e474d9e7808addd85a5bca18af5035d45d0598a`

Übernommen wurden ausschließlich Architektur- und Sicherheitsmuster: getrennte Environment Secrets, Caddy/Compose-Konventionen, OIDC über anwendungsspezifische Authentik-Entitlements, eingeschränkte technische Nextcloud-Konten sowie Pretix-Paginierung, Timeout-, Cache-, Fehler- und SSRF-Regeln. Es besteht keine Laufzeitabhängigkeit zu einem dieser Repositories.

