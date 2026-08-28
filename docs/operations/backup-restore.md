# Backup und Wiederherstellung

Ein fachlich vollständiges Werkblatt-Backup besteht immer aus zwei gemeinsam datierten Teilen:

1. einem konsistenten PostgreSQL-Dump mit `pg_dump --format=custom`;
2. dem vollständigen privaten Medien-Volume mit Asset-Originalen, PNG-Renditions und erzeugten PDFs.

Secrets und die produktive `.env` gehören nicht in das Backup-Repository. Die Deployment-Konfiguration wird getrennt versioniert; Secrets werden aus dem zuständigen Secret Store wiederhergestellt.

## Ablauf

- Anwendung für den kurzen Konsistenzpunkt in Wartungsmodus versetzen oder Datenbank- und Volume-Snapshot auf derselben Storage-Ebene erstellen.
- PostgreSQL-Dump erzeugen und Prüfsumme bilden.
- privates Medien-Volume vollständig sichern und Prüfsumme/Dateiliste bilden.
- beide Teile verschlüsselt, zugriffsbeschränkt und mit gemeinsamer Backup-ID ablegen.
- Restore regelmäßig in eine isolierte Umgebung durchführen: leere Datenbank anlegen, `pg_restore --clean --if-exists` ausführen, Medienbaum wiederherstellen, Migrationen prüfen.

Nach dem Restore werden mindestens Organisationen, Workshops, Dokumentationsrevisionen und Hashes, Custom Fields, Vorlagenstände, historische Asset-Versionen sowie GeneratedDocument-Dateizuordnungen geprüft. `tests/security/test_backup_restore.py` bildet diesen Graphen einschließlich privater Dateien synthetisch nach; der infrastrukturelle PostgreSQL-/Volume-Restore bleibt ein wiederkehrender Betriebscheck.
