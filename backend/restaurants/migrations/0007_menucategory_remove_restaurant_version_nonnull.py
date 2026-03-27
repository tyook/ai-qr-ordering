# Migration 3 of 3: Remove restaurant FK from MenuCategory, make version non-nullable.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('restaurants', '0006_data_create_default_menu_versions'),
    ]

    operations = [
        # Remove the old restaurant FK from MenuCategory
        migrations.RemoveField(
            model_name='menucategory',
            name='restaurant',
        ),
        # Make version FK non-nullable now that all rows are assigned
        migrations.AlterField(
            model_name='menucategory',
            name='version',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='categories',
                to='restaurants.menuversion',
            ),
        ),
    ]
