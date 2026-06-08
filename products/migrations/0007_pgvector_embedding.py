"""
Adds the pgvector extension to Postgres and an `embedding` VectorField
to the Product model for AI visual search.

The CREATE EXTENSION runs as a no-op if the extension already exists
(the docker-compose init script enables it on first boot too — this
migration is the belt-and-braces version for non-Docker environments).
"""

from django.db import migrations, models
import pgvector.django


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0006_product_brand_product_original_price_product_rating'),
    ]

    operations = [
        pgvector.django.VectorExtension(),
        migrations.AddField(
            model_name='product',
            name='embedding',
            field=pgvector.django.VectorField(
                blank=True, dimensions=512, null=True
            ),
        ),
        migrations.AddField(
            model_name='product',
            name='embedding_updated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
