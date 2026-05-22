"""
Signal handlers for the products app.

We re-compute a product's CLIP embedding whenever its main image changes
(or its first image is created). The signal only enqueues the Celery
task — the heavy lifting is async so request latency is unaffected.
"""

from __future__ import annotations

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from products.models import ProductImage

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ProductImage)
def queue_embedding_on_image_save(sender, instance: ProductImage, created: bool, **kwargs):
    """Enqueue an embedding job whenever a ProductImage is created or set as main."""
    # Avoid importing the task at module import time so apps load cleanly
    # even if the celery worker isn't running.
    from products.tasks import embed_product_image

    # Only re-embed when this image is (or just became) the main image,
    # or when it's the only image the product has.
    if instance.is_main or not instance.product.images.exclude(pk=instance.pk).exists():
        try:
            embed_product_image.delay(instance.product_id)
        except Exception:
            logger.exception("Failed to enqueue embedding for product %s", instance.product_id)
