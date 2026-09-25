from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("identities", "0003_membership_editor_role"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="preferred_workshop_view",
            field=models.CharField(
                choices=[("calendar", "Kalender"), ("list", "Liste")],
                default="calendar",
                max_length=16,
            ),
        ),
    ]
