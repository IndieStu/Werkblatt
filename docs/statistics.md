# Organisationsbezogene Statistik

Werkblatt stellt angemeldeten Workshop Usern, Editoren und Organization Admins
eine tenantgebundene Statistikansicht unter `/documentation/statistics/` bereit.
Sie enthält keine Teilnehmer:innen-, Workshop- oder Benutzernamen. Der
CSV-Export bildet ausschließlich dieselben aggregierten Werte ab.

## Datenbasis und Revisionen

Der Zeitraum bezieht sich auf das Datum des Workshops. Pro Dokumentation wird
höchstens die neueste abgeschlossene, unveränderliche Revision ausgewertet.
Ältere Revisionen werden niemals addiert. Ist eine Dokumentation zur Korrektur
wieder geöffnet, bleibt die letzte abgeschlossene Revision die statistische
Grundlage; die Ansicht weist diesen Zustand zusätzlich als „Korrektur
ausstehend“ aus. Workshops ohne abgeschlossene Revision fließen nur in die
Zahlen „Workshops“ und „Ohne Abschluss“ ein. Workshops mit der begründeten
Entscheidung „Keine Dokumentation erforderlich“ werden separat gezählt und
nicht als fehlender Abschluss behandelt.

## Kennzahlen

- Workshops im gewählten Zeitraum
- Workshops mit beziehungsweise ohne Abschluss
- Dokumentationen mit geöffneter Korrektur
- angemeldete und davon anwesende Personen
- No-Shows
- spontane Teilnahmen
- Teilnahmen insgesamt
- Anwesenheitsquote der angemeldeten Personen
- numerische Custom Fields mit `presentation = aggregate_statistic`

Die Anwesenheitsquote verwendet `present_registered / registered`. Spontane
Teilnahmen stehen separat und können die Quote daher nicht über 100 Prozent
heben. Aggregierte Custom Fields werden anhand ihres im Snapshot eingefrorenen
Labels summiert und zusätzlich nach Projekt und Dokumentvorlage gruppiert.

## Datenschutz und Tenant-Isolation

Alle Abfragen beginnen mit dem serverseitig validierten Organisationskontext.
Requestparameter können keine Organisation auswählen. Der CSV-Export enthält
weder Teilnehmendennamen noch Workshoptitel, Benutzerkennungen oder
Freitextberichte. Cross-Tenant- und Revisionsregeln sind automatisiert getestet.

Die Statistik ist eine operative Auswertung und kein behördliches oder
revisionspflichtiges Fachverfahren. Ihre Nachvollziehbarkeit entsteht aus den
unveränderlichen Dokumentationsrevisionen, nicht aus einem separaten
Statistikdatenbestand.
