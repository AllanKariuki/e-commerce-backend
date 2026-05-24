"""
Adds the ``SearchQuery`` model — one row per ``POST /api/search/visual``
call, capturing the resized query image URL, the ordered top result
product IDs, latency, and the user/session that issued it. Used later
for visual-search relevance tuning.
"""

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0007_pgvector_embedding'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SearchQuery',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True, serialize=False, verbose_name='ID',
                )),
                ('image_url', models.URLField(max_length=500)),
                ('top_result_ids', ArrayField(
                    base_field=models.IntegerField(),
                    blank=True,
                    default=list,
                    size=None,
                )),
                ('latency_ms', models.PositiveIntegerField(blank=True, null=True)),
                ('result_count', models.PositiveIntegerField(default=0)),
                ('session_key', models.CharField(blank=True, default='', max_length=128)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=models.deletion.SET_NULL,
                    related_name='search_queries',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['-created_at'], name='prod_sq_created_idx'),
                    models.Index(fields=['user', '-created_at'], name='prod_sq_user_created_idx'),
                ],
            },
        ),
    ]
