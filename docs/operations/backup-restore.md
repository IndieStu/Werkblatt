# Backup und Wiederherstellung

Ein fachlich vollständiges Werkblatt-Backup besteht immer aus zwei gemeinsam datierten Teilen:

1. einem konsistenten PostgreSQL-Dump mit `pg_dump --format=custom`;
2. dem vollständigen privaten Medien-Volume mit Asset-Originalen, PNG-Renditions und erzeugten PDFs.

Secrets und die produktive `.env` gehören nicht in Git. Der bestehende Zircula-Restic-Lauf sichert `/srv/zircula` einschließlich der Werkblatt-Secrets verschlüsselt; Zugriff, Rotation und Wiederherstellung der Credentials bleiben gesondert zu protokollieren. Die Deployment-Konfiguration wird versioniert.

## Ablauf

- Anwendung für den kurzen Konsistenzpunkt in Wartungsmodus versetzen oder Datenbank- und Volume-Snapshot auf derselben Storage-Ebene erstellen.
- PostgreSQL-Dump erzeugen und Prüfsumme bilden.
- privates Medien-Volume vollständig sichern und Prüfsumme/Dateiliste bilden.
- beide Teile verschlüsselt, zugriffsbeschränkt und mit gemeinsamer Backup-ID ablegen.
- Restore regelmäßig in eine isolierte Umgebung durchführen: leere Datenbank anlegen, `pg_restore --clean --if-exists` ausführen, Medienbaum wiederherstellen, Migrationen prüfen.

Nach dem Restore werden mindestens Organisationen, Workshops, Dokumentationsrevisionen und Hashes, Custom Fields, Vorlagenstände, historische Asset-Versionen sowie GeneratedDocument-Dateizuordnungen geprüft. `tests/security/test_backup_restore.py` bildet diesen Graphen einschließlich privater Dateien synthetisch nach; der infrastrukturelle PostgreSQL-/Volume-Restore bleibt ein wiederkehrender Betriebscheck.

## Zircula-VPS

Der vorhandene tägliche Backup-Lauf sichert `/srv/zircula`, die Infrastrukturkonfiguration und Staging mit Restic und repliziert anschließend auf das getrennte nctest-System. Für den eigenen Werkblatt-PostgreSQL-Container muss er vor dem Restic-Snapshot zusätzlich einen logischen Dump erzeugen; die rohen Dateien unter `/srv/zircula/werkblatt/postgres` werden nicht als primäre Restore-Quelle verwendet. Vor jeder Werkblatt-Aktualisierung wird zusätzlich ein eindeutig datierter Custom-Dump erstellt und der Medienstand gesichert. Ein Rollback stellt Datenbank und Medien aus derselben Backup-ID wieder her; ein bloßes Zurückrollen des Containers genügt nach einer nicht rückwärtskompatiblen Migration nicht.

Ein Restore-Test darf niemals in die produktive Werkblatt-Datenbank schreiben. Er verwendet eine isolierte temporäre Datenbank, ein temporäres Medienverzeichnis und das exakt zu prüfende Container-Image. Nach erfolgreicher Prüfung werden Anzahl und Hashes der synthetischen Snapshots sowie die Abrufbarkeit der synthetischen PDF-Datei verglichen.
