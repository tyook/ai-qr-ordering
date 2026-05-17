from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("restaurants", "0020_operating_hours_multi_slot"),
    ]

    operations = [
        migrations.AddField(
            model_name="restaurant",
            name="accepting_orders",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="restaurant",
            name="auto_resume_orders",
            field=models.BooleanField(default=True),
        ),
    ]
