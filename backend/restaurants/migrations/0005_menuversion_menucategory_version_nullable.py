# Migration 1 of 3: Add MenuVersion model + add nullable version FK to MenuCategory
# (restaurant FK kept temporarily for data migration in next step)

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('restaurants', '0004_restaurant_estimated_minutes_per_order'),
    ]

    operations = [
        migrations.CreateModel(
            name='MenuVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('is_active', models.BooleanField(default=False)),
                ('source', models.CharField(
                    choices=[('manual', 'Manual'), ('ai_upload', 'AI Upload')],
                    default='manual',
                    max_length=20,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('restaurant', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='menu_versions',
                    to='restaurants.restaurant',
                )),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddField(
            model_name='menucategory',
            name='version',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='categories',
                to='restaurants.menuversion',
            ),
        ),
    ]
