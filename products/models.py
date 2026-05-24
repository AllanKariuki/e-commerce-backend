from django.db import models
from users.models import User
from django.contrib.postgres.fields import ArrayField
from pgvector.django import VectorField

# Create your models here.
class ProductCategory(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()

    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(ProductCategory, on_delete=models.CASCADE)
    units_in_stock = models.IntegerField()
    sizes = ArrayField(models.CharField(max_length=10), blank=True, null=True)
    colors = ArrayField(models.CharField(max_length=30), blank=True, null=True)
    material = models.CharField(max_length=50, blank=True, null=True)
    rating = models.FloatField(default=0.0)
    original_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    brand = models.CharField(max_length=50, blank=True, null=True)

    # CLIP ViT-B/32 image embedding (512-dim). Populated by
    # products.tasks.embed_product_image (Celery) on save / image change.
    # Null until the first embedding job completes.
    embedding = VectorField(dimensions=512, null=True, blank=True)
    embedding_updated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name
    
class ProductImage(models.Model):
    product = models.ForeignKey(Product, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to="products_images", null=True, blank=True)
    is_main = models.BooleanField(default=False)

    def __str__(self) :
        return f"Image for {self.product.name}"
    
class Review(models.Model):
    product = models.ForeignKey(Product, related_name='reviews', on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name='reviews', on_delete=models.CASCADE)
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review for {self.product.name} by {self.user.username}"


class SearchQuery(models.Model):
    """One row per call to ``POST /api/search/visual``.

    Captured so we can later (a) measure relevance — did the shopper
    click any of the returned products? (b) spot slow-path latency
    regressions in Replicate / Cloudinary, and (c) build a corpus of
    real-user query images to fine-tune ranking on. We deliberately
    store the *Cloudinary URL* of the resized query image rather than
    re-uploading or re-embedding here; the view already paid that
    cost.

    Either ``user`` or ``session_key`` will normally be populated
    (matching the guest-cookie convention used elsewhere); both can
    be null for an anonymous request that doesn't carry a guest
    cookie yet.
    """

    # Image the user uploaded, after server-side resize (the 256px
    # JPEG actually fed into Replicate, not the original upload). Stored
    # as a Cloudinary secure_url string — Cloudinary owns the bytes.
    image_url = models.URLField(max_length=500)

    # Ordered list of Product IDs returned to the client, best match
    # first. ArrayField rather than M2M because (1) the same product
    # can appear once per query so order matters more than uniqueness,
    # (2) we never join from Product back to SearchQuery, and (3) we
    # already use ArrayField elsewhere in this app for ``sizes`` /
    # ``colors`` so the dependency is in scope.
    top_result_ids = ArrayField(models.IntegerField(), default=list, blank=True)

    # End-to-end wall-clock latency the view reported to the client.
    # Useful for spotting regressions when Replicate is slow.
    latency_ms = models.PositiveIntegerField(null=True, blank=True)

    # How many results we returned (≤ the ``limit`` query param).
    result_count = models.PositiveIntegerField(default=0)

    # Authed user, if any. SET_NULL so we keep the relevance signal
    # if the user later deletes their account.
    user = models.ForeignKey(
        User,
        related_name='search_queries',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    # Guest-cookie value (matches the ``guest:<uuid>`` shape used by
    # ProductViewSet._get_user_identifier). Free-form string rather
    # than FK because guest sessions aren't a first-class model.
    session_key = models.CharField(max_length=128, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        who = (
            f"user:{self.user_id}" if self.user_id
            else (f"guest:{self.session_key}" if self.session_key else "anon")
        )
        return f"SearchQuery({who}, {self.result_count} results, {self.latency_ms or '?'}ms)"