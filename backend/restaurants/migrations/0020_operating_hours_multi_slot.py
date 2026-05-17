from django.db import migrations, models


def remove_closed_rows(apps, schema_editor):
    OperatingHours = apps.get_model("restaurants", "OperatingHours")
    OperatingHours.objects.filter(is_closed=True).delete()
    OperatingHours.objects.filter(open_time__isnull=True).delete()
    OperatingHours.objects.filter(close_time__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("restaurants", "0019_operating_hours"),
    ]

    operations = [
        migrations.RunPython(remove_closed_rows, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="operatinghours",
            name="is_closed",
        ),
        migrations.AlterField(
            model_name="operatinghours",
            name="open_time",
            field=models.TimeField(),
        ),
        migrations.AlterField(
            model_name="operatinghours",
            name="close_time",
            field=models.TimeField(),
        ),
        migrations.AlterUniqueTogether(
            name="operatinghours",
            unique_together=set(),
        ),
        migrations.AlterModelOptions(
            name="operatinghours",
            options={"ordering": ["day_of_week", "open_time"]},
        ),
    ]
