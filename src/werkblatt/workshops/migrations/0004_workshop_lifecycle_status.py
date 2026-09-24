from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("workshops", "0003_workshop_documentation_requirement_and_more")]

    operations = [
        migrations.AddField(
            model_name="workshop",
            name="lifecycle_status",
            field=models.CharField(
                choices=[("active", "Aktiv"), ("cancelled", "Abgesagt")],
                default="active",
                max_length=16,
            ),
        ),
    ]
