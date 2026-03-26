from django.db import migrations
from django.db.models import F


def backfill_confirmed_at(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    Order.objects.filter(
        status__in=["confirmed", "preparing", "ready", "completed"],
        confirmed_at__isnull=True,
    ).update(confirmed_at=F("created_at"))


def reverse_backfill(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    Order.objects.filter(confirmed_at__isnull=False).update(confirmed_at=None)


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0003_order_completed_at_order_confirmed_at_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_confirmed_at, reverse_backfill),
    ]
