# Migration 2 of 3: Data migration — create default MenuVersion per restaurant,
# assign all existing MenuCategory rows to it.

from django.db import migrations


def create_default_versions(apps, schema_editor):
    Restaurant = apps.get_model('restaurants', 'Restaurant')
    MenuVersion = apps.get_model('restaurants', 'MenuVersion')
    MenuCategory = apps.get_model('restaurants', 'MenuCategory')

    for restaurant in Restaurant.objects.all():
        version = MenuVersion.objects.create(
            restaurant=restaurant,
            name='Default',
            is_active=True,
            source='manual',
        )
        MenuCategory.objects.filter(restaurant=restaurant).update(version=version)


def reverse_default_versions(apps, schema_editor):
    MenuVersion = apps.get_model('restaurants', 'MenuVersion')
    MenuCategory = apps.get_model('restaurants', 'MenuCategory')

    # Clear version FK on all categories before removing MenuVersion rows
    MenuCategory.objects.all().update(version=None)
    MenuVersion.objects.filter(name='Default').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('restaurants', '0005_menuversion_menucategory_version_nullable'),
    ]

    operations = [
        migrations.RunPython(create_default_versions, reverse_default_versions),
    ]
