# Rollen und fachliche Berechtigungen

Werkblatt verwendet genau drei feste Rollen. Die Autorisierung wird zentral über
fachliche Capabilities umgesetzt; Rollen oder Rechte sind nicht frei
konfigurierbar. Jede Berechtigung gilt ausschließlich in der aktiven
Organisation.

| Fähigkeit | Workshop User | Editor | Organization Admin |
|---|---:|---:|---:|
| Workshops sehen und dokumentieren | ja | ja | ja |
| Dokumentationen finalisieren und Vorlagen verwenden | ja | ja | ja |
| Organisationsstatistik und aggregierten CSV-Export sehen | ja | ja | ja |
| Dokumentvorlagen, Custom Fields und Ausgaben verwalten | nein | ja | ja |
| Dokumentvorlagen duplizieren und sicher archivieren | nein | ja | ja |
| Dokumentbezogene Assets hochladen und verwalten | nein | ja | ja |
| Vorhandene Organisationsassets in Vorlagen verwenden | ja | ja | ja |
| Organisationsassets und Organisationsbranding verwalten | nein | nein | ja |
| Organisationsprofil ändern | nein | nein | ja |
| Integrationen konfigurieren | nein | nein | ja |
| Memberships und Rollen verwalten | nein | nein | ja |

„Dokumentbezogene Assets“ umfasst Förder-, Projekt-, Auftraggeber- und sonstige
für Dokumentausgaben verwendete Logos. Die Asset-Bibliothek bleibt gemeinsam:
Ein Editor kann ein darin vorhandenes Organisationslogo in einer Vorlage
auswählen, darf aber weder Datei noch Version, Metadaten, Kategorie oder
Branding-Funktion dieses Assets verändern.

Organization Admin besitzt alle Rechte von Editor und Workshop User. Editor
besitzt alle operativen Rechte von Workshop User. Diese fachliche Hierarchie
wird als feste Capability-Zuordnung ausgedrückt und ist keine konfigurierbare
Rollenvererbung.

Bestehende Memberships werden bei Einführung von Editor nicht verändert. Die
OIDC-Zuordnung folgt der Priorität Organization Admin, Editor, Workshop User.
