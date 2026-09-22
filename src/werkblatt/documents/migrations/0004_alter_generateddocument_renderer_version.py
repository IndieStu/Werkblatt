from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0003_alter_generateddocument_renderer_version_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="generateddocument",
            name="renderer_version",
            field=models.CharField(default="weasyprint-70/v1", max_length=32),
        ),
    ]
