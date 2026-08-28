from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("workshops", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="workshopregistration",
            name="active",
            field=models.BooleanField(default=True),
        )
    ]
