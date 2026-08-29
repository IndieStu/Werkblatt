# Persönliche Einstellungen und Organisationsverwaltung

Werkblatt trennt persönliche Präferenzen strikt von organisationsweiten Werten.

## Persönliche Einstellungen

`/settings/` steht jedem angemeldeten Benutzer zur Verfügung. Die Werte werden am
Benutzerkonto gespeichert und verändern weder die Organisation noch deren
Vorlagen, Assets oder Integrationen.

- Erscheinungsbild: Hell, Dunkel oder Systemeinstellung. „Systemeinstellung“
  folgt im Browser `prefers-color-scheme`.
- Sprache: Die Präferenz ist strukturell am Benutzer vorgesehen. V1 bietet
  ausschließlich Deutsch an, solange keine weitere Sprache vollständig
  übersetzt und getestet ist.

Der Dark Mode leitet sich ausschließlich aus den bestehenden Werkblatt-Tokens
und Markenfarben ab. Die PDF-Ausgaben sind davon unabhängig.

## Organisationsverwaltung

`/administration/` ist Organization Admins vorbehalten und umfasst derzeit das
Organisationsprofil, Logos und Assets sowie Dokumentvorlagen. Später gehören
auch Organisationsbranding, Integrationen und weitere organisationsweite
Konfiguration hierher. Diese Erweiterungen werden nicht vorab als leere
Architekturschichten implementiert.
