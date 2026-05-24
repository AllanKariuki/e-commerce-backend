"""
Celery tasks for the products app.

The headline task here is `embed_product_image`, which computes a 512-dim
CLIP image embedding via Replicate and stores it on the Product row. The
embedding powers the visual-search endpoint (see roadmap in BUILD_PLAN.md).

Why Replicate instead of running CLIP locally:
  - No 600MB+ model baked into the Docker image
  - No cold-start at first request
  - ~$0.00057 per embedding — negligible at MVP scale
  - Same API path is reused for user search-query images
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


def embed_image_url(image_url: str) -> Optional[list[float]]:
    """
    Call Replicate's CLIP embedding model and return a 512-float vector.
    Returns None on failure so callers can decide whether to retry.

    Public helper so both the Celery task layer and the synchronous
    request path (e.g. ``products.views.VisualSearchView``) can share
    the same embedding code. Replicate is imported lazily so the worker
    boots even if the package isn't installed yet (useful during early
    bootstrap when devs first build the image without the new
    requirements pinned in).
    """
    try:
        import replicate  # type: ignore
    except ImportError:
        logger.error("replicate package not installed; skipping embedding")
        return None

    token = os.getenv("REPLICATE_API_TOKEN")
    if not token:
        logger.warning("REPLICATE_API_TOKEN not set; skipping embedding")
        return None

    try:
        # krthr/clip-embeddings returns {"embedding": [...512 floats...]}
        output = replicate.run(
            "krthr/clip-embeddings:1c0371070cb827ec3c7f2f28adcdde54b50dcd239aa6faea0bc98b174ef03fb4",
            input={"input": image_url},
        )
        if isinstance(output, dict) and "embedding" in output:
            return list(output["embedding"])
        # Some Replicate versions return the bare list
        if isinstance(output, list) and len(output) == 512:
            return [float(x) for x in output]
        logger.error("Unexpected Replicate response shape: %r", type(output))
        return None
    except Exception:
        logger.exception("Replicate embedding failed for %s", image_url)
        return None


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
    name="products.tasks.embed_product_image",
)
def embed_product_image(self, product_id: int) -> str:
    """
    Compute and persist the CLIP embedding for a Product, based on its
    main image (or first image if none are flagged main).

    Idempotent: rerunning replaces the existing vector.
    """
    # Imported here to avoid AppRegistryNotReady at worker import time.
    from products.models import Product

    try:
        product = Product.objects.get(pk=product_id)
    except Product.DoesNotExist:
        logger.warning("Product %s no longer exists; skipping embedding", product_id)
        return "skipped:gone"

    image = (
        product.images.filter(is_main=True).first()
        or product.images.first()
    )
    if image is None or not image.image:
        logger.info("Product %s has no image; skipping embedding", product_id)
        return "skipped:no-image"

    # Cloudinary returns a full HTTPS URL via .url
    image_url = image.image.url
    if not image_url.startswith("http"):
        logger.info("Image URL not yet accessible (%s); will retry", image_url)
        raise self.retry(countdown=30)

    vector = embed_image_url(image_url)
    if vector is None:
        return "skipped:embed-failed"

    Product.objects.filter(pk=product_id).update(
        embedding=vector,
        embedding_updated_at=timezone.now(),
    )
    logger.info("Embedded product %s (dim=%d)", product_id, len(vector))
    return f"ok:{product_id}"


@shared_task(name="products.tasks.embed_missing_products")
def embed_missing_products(limit: int = 100) -> int:
    """
    Periodic sweep: enqueue embedding for products that don't have one yet.
    Hooked up via celery-beat in settings.CELERY_BEAT_SCHEDULE.
    """
    from products.models import Product

    qs = Product.objects.filter(embedding__isnull=True).values_list("id", flat=True)[:limit]
    count = 0
    for pid in qs:
        embed_product_image.delay(pid)
        count += 1
    logger.info("Enqueued %d products for embedding", count)
    return count
