# Authentik-Vorbereitung für Werkblatt

Diese Konfiguration wird erst für den integrierten Test angelegt. Werkblatt benötigt weder Authentik-Adminrechte noch eine Laufzeitverbindung zur Admin-API.

## Vorgesehene Werte

| Einstellung | Wert |
|---|---|
| Application/Provider | `Werkblatt` |
| Application slug | `werkblatt` |
| Client type | Confidential |
| Grant type | Authorization Code |
| PKCE | S256 |
| Redirect URI | `<PUBLIC_BASE_URL>/auth/oidc/callback/` |
| Post-logout-Ziel | `<PUBLIC_BASE_URL>/` |
| Subject mode | UUID-basiertes stabiles Subject |
| Issuer mode | eigener Issuer je Application-Slug |
| Erwartete Discovery-URL | `<AUTHENTIK_BASE_URL>/application/o/werkblatt/.well-known/openid-configuration` |
| Scopes | `openid email profile groups` |

Die erwartete Discovery-URL wird bei der tatsächlichen Einrichtung in Authentik bestätigt und nicht allein aufgrund des Namens als produktiv vorausgesetzt.

## Berechtigungen

Vorgesehene anwendungsspezifische Entitlements beziehungsweise Claims:

- `Werkblatt Admins` -> `Organization Admin`
- `Werkblatt Editors` -> `Editor`
- `Werkblatt Users` -> `Workshop User`

Nur Werkblatt-spezifische Entitlements dürfen im Gruppenclaim ankommen. Authentik-interne Admin-Gruppen oder Nextcloud-Entitlements gewähren keinen Werkblatt-Zugriff. Fehlt eine erlaubte Gruppe, verweigert Werkblatt die Provisionierung.

## Secret-Übergabe

1. Provider unmittelbar vor dem integrierten Test anlegen.
2. Client-ID in die lokale geschützte `.env` eintragen.
3. Client-Secret ausschließlich als geschützte Secret-Datei der Deployment-Plattform hinterlegen; nicht in `.env`.
4. Secret-Verzeichnis und Datei nach dem Least-Privilege-Prinzip schützen.
5. Konfiguration ausschließlich mit `docker compose config --quiet` prüfen.
6. Secret niemals in Git, Chat, Screenshots oder Logs kopieren.

## Abnahmetest

- erfolgreicher Login eines `Workshop User`;
- erfolgreicher Login eines `Editor`;
- erfolgreicher Login eines `Organization Admin`;
- Ablehnung eines Benutzers ohne Werkblatt-Entitlement;
- stabile Wiedererkennung über `(issuer, sub)` trotz geändertem Anzeigenamen/E-Mail;
- Session-Rotation und Logout;
- kein Nextcloud- oder Authentik-Adminrecht durch implizite Gruppennamen;
- schmaler Viewport und MFA-Flow bleiben verwendbar.
