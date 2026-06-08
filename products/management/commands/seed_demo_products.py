"""
Seed sample wig / hair-extension products into the catalog.

This exists so the visual-search and hair-try-on pipelines have realistic
catalog data to chew on during local development and demos. It is NOT a
production fixture — products are randomized within fixed templates and
images are placeholder photos, not licensed product shots.

Usage
-----

    python manage.py seed_demo_products
        # 30 products, picsum placeholder image each, NO embedding jobs.

    python manage.py seed_demo_products --count 20
        # Limit to 20 products.

    python manage.py seed_demo_products --no-images
        # Skip ProductImage creation entirely (useful when Cloudinary
        # creds aren't configured locally).

    python manage.py seed_demo_products --enqueue-embeddings
        # Allow the post_save signal to fire on ProductImage save so the
        # Celery worker queues Replicate CLIP embedding jobs. OFF by
        # default so re-running the seeder doesn't burn Replicate credits.

    python manage.py seed_demo_products --clear
        # Delete previously-seeded products (any Product whose `brand`
        # matches one of the demo brands) before reseeding.

Safety notes
------------

* The default run does NOT enqueue Replicate jobs. The embedding
  ``post_save`` handler is temporarily disconnected for the duration of
  the run and reconnected in ``finally`` so global signal state is left
  untouched.
* Images are fetched from picsum.photos using a deterministic seed
  derived from the product slug, so reruns produce the same image set
  for the same products. Picsum images are not real wig photos — they
  exist purely so the embedding + storage pipelines have *something*
  end-to-end testable. Swap them out via the admin for serious visual
  search work.
* If image upload to Cloudinary fails (no network, bad creds), the
  product is still created without an image rather than rolling back
  the whole batch.
"""

from __future__ import annotations

import logging
import random
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models.signals import post_save

logger = logging.getLogger(__name__)

# -- Demo data ---------------------------------------------------------------

CATEGORY_NAME = "Wigs & Hair Extensions"
CATEGORY_DESCRIPTION = (
    "Synthetic, human, and blended wigs, weaves, braids and extensions. "
    "Primary catalog category for the TryOn.ke MVP — the AI hair try-on "
    "pipeline matches user selfies against products tagged here."
)

# Brand names common in the Kenyan wig market. Mix of real distributors
# and generic descriptors; none of these encode pricing or imply
# endorsement. Used both for product generation and for the --clear
# selector, so anything added here should be considered "demo data."
BRANDS = [
    "Darling",
    "Sleek",
    "X-Pression",
    "Bobbi Boss",
    "Outré",
    "Sensationnel",
    "RastAfri",
    "Tresses",
    "Janet Collection",
    "Modu",
]

COLORS_POOL = [
    "Natural Black",
    "Jet Black",
    "Dark Brown",
    "Medium Brown",
    "Honey Blonde",
    "Caramel",
    "Auburn",
    "Burgundy",
    "Wine Red",
    "Ombre Black/Honey",
    "Ombre Black/Burgundy",
    "Mixed Highlights",
    "Ash Grey",
    "Platinum Blonde",
]

LENGTHS = [
    '8"', '10"', '12"', '14"', '16"', '18"', '20"', '22"', '24"', '26"', '28"', '30"',
]

MATERIALS = [
    "100% Synthetic",
    "Heat-Resistant Synthetic",
    "Human Hair Blend",
    "100% Human Hair",
    "Brazilian Human Hair",
]

# (style, base_name, price_low_ksh, price_high_ksh)
# Prices in Kenyan Shillings, matching the AOV band (KSh 5K-50K) called
# out in AI_Ecommerce_Kenya_Strategy.docx. Random price is sampled
# uniformly within each row's band.
WIG_TEMPLATES = [
    ("braided",  "Box Braids Lace Front Wig",         8500, 18000),
    ("braided",  "Goddess Box Braids Wig",            9000, 21000),
    ("braided",  "Knotless Braids Full Wig",          7500, 16000),
    ("braided",  "Senegalese Twist Braided Wig",      8200, 17500),
    ("braided",  "Cornrow Braided Headband Wig",      4500,  9500),
    ("kinky",    "Kinky Curly Afro Wig",              5500, 12000),
    ("kinky",    "Kinky Straight Lace Wig",           7000, 15500),
    ("kinky",    "4C Natural Afro Puff Wig",          4200,  9000),
    ("curly",    "Deep Curly Lace Front Wig",         6800, 14500),
    ("curly",    "Water Wave Bundle Wig",            10000, 24000),
    ("curly",    "Loose Curl Glueless Wig",           9500, 22000),
    ("straight", "Silky Straight Bone Wig",          11000, 26000),
    ("straight", "Yaki Straight Lace Closure Wig",    9000, 21000),
    ("straight", "Pixie Cut Short Straight Wig",      5500, 12000),
    ("bob",      "Blunt Cut Bob Lace Wig",            6500, 14000),
    ("bob",      "Asymmetrical Lob Wig",              7200, 15500),
    ("bob",      "Curly Bob with Bangs",              7000, 15000),
    ("lace",     "13x4 HD Lace Front Wig",           14000, 38000),
    ("lace",     "Full Lace Glueless Wig",           18000, 45000),
    ("lace",     "5x5 Closure Lace Wig",             12000, 32000),
    ("ponytail", "Drawstring High Ponytail",          2500,  6500),
    ("ponytail", "Long Wavy Clip-In Ponytail",        3500,  8000),
    ("half",     "Headband Half Wig",                 3800,  8500),
    ("half",     "Drawstring Half Wig with Bangs",    4200,  9500),
    ("weave",    "Brazilian Body Wave Bundle",        4500, 12000),
    ("weave",    "Peruvian Deep Wave 3-Bundle Set",  13500, 29000),
    ("weave",    "Malaysian Straight Bundle",         5200, 13000),
    ("frontal",  "13x6 Transparent Lace Frontal",     7500, 18000),
    ("frontal",  "4x4 HD Lace Closure",               4800, 11500),
    ("frontal",  "Pre-Plucked Lace Closure",          5500, 13000),
]


# -- Command -----------------------------------------------------------------


class Command(BaseCommand):
    help = (
        "Seed sample wig / hair-extension products for development and demos. "
        "Safe by default — does NOT enqueue Replicate embedding jobs unless "
        "--enqueue-embeddings is passed."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=30,
            help=(
                "Number of products to create. Capped at the number of templates "
                "currently defined (%d)." % len(WIG_TEMPLATES)
            ),
        )
        parser.add_argument(
            "--no-images",
            action="store_true",
            help="Skip ProductImage creation. Useful when Cloudinary is not configured.",
        )
        parser.add_argument(
            "--enqueue-embeddings",
            action="store_true",
            help=(
                "Allow the post_save signal to fire and enqueue Replicate "
                "embedding jobs. OFF by default so reruns don't burn credits."
            ),
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help=(
                "Delete existing demo products (brand IN demo-brands, "
                "category=Wigs & Hair Extensions) before seeding."
            ),
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=42,
            help="Random seed for reproducibility (default: 42).",
        )

    def handle(self, *args, **options):
        # Local imports keep this module importable even if Django apps
        # aren't loaded yet (e.g. during static analysis).
        from products.models import Product, ProductCategory, ProductImage
        from products.signals import queue_embedding_on_image_save

        count = options["count"]
        if count <= 0:
            raise CommandError("--count must be positive")
        count = min(count, len(WIG_TEMPLATES))

        random.seed(options["seed"])

        if options["clear"]:
            self._clear(Product)

        category, created = ProductCategory.objects.get_or_create(
            name=CATEGORY_NAME,
            defaults={"description": CATEGORY_DESCRIPTION},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created category: {category.name}"))

        enqueue = options["enqueue_embeddings"]
        signal_was_disconnected = False
        if not enqueue:
            # Disconnect the embedding-enqueue signal for the duration
            # of the seed so Replicate credits are not spent. Reconnect
            # in `finally` to keep global state pristine.
            signal_was_disconnected = post_save.disconnect(
                queue_embedding_on_image_save, sender=ProductImage,
            )
            self.stdout.write(
                self.style.WARNING(
                    "Embedding signal DISCONNECTED for this run — pass "
                    "--enqueue-embeddings to populate vectors via Replicate."
                )
            )

        skip_images = options["no_images"]

        try:
            with transaction.atomic():
                created_count = 0
                for template in WIG_TEMPLATES[:count]:
                    style, base_name, price_low, price_high = template
                    product = self._create_product(
                        Product, category, style, base_name, price_low, price_high,
                    )
                    if not skip_images:
                        self._attach_image(ProductImage, product)
                    created_count += 1
                    self.stdout.write(f"  + {product.name}  [KSh {product.price}]")
                self.stdout.write(
                    self.style.SUCCESS(f"Seeded {created_count} products in '{category.name}'.")
                )
        finally:
            if signal_was_disconnected:
                post_save.connect(queue_embedding_on_image_save, sender=ProductImage)

    # -- helpers ------------------------------------------------------------

    def _clear(self, Product):
        deleted, _ = Product.objects.filter(brand__in=BRANDS).delete()
        self.stdout.write(
            self.style.WARNING(f"Cleared {deleted} pre-existing demo product rows")
        )

    def _create_product(self, Product, category, style, base_name, price_low, price_high):
        brand = random.choice(BRANDS)
        price = Decimal(random.randint(price_low, price_high))
        # Roughly 40% of products get a slashed "original_price" to drive
        # discount-percentage UI on the frontend.
        original_price = (
            (price * Decimal("1.20")).quantize(Decimal("1."))
            if random.random() < 0.4
            else None
        )
        length = random.choice(LENGTHS)
        material = random.choice(MATERIALS)
        colors = random.sample(COLORS_POOL, k=random.randint(2, 4))
        description = self._build_description(brand, base_name, style, length, material)

        return Product.objects.create(
            name=f"{brand} {base_name} – {length}",
            description=description,
            price=price,
            original_price=original_price,
            category=category,
            units_in_stock=random.randint(5, 80),
            sizes=[length],
            colors=colors,
            material=material,
            brand=brand,
            rating=round(random.uniform(3.8, 4.9), 1),
        )

    def _build_description(self, brand, base_name, style, length, material):
        details = [
            f"Brand: {brand}",
            f"Length: {length}",
            f"Material: {material}",
            f"Style: {style}",
            "Ships within 24h from Nairobi.",
            "M-Pesa-only checkout (sandbox during MVP).",
        ]
        return (
            f"Premium {style} wig from {brand}. Curated for the TryOn.ke "
            f"hair try-on experience. " + " | ".join(details)
        )

    def _attach_image(self, ProductImage, product):
        """Fetch a deterministic placeholder image and attach as the main ProductImage.

        Errors are logged but non-fatal — a transient network failure
        shouldn't roll back the whole catalog seed.
        """
        seed = f"tryonke-{product.pk}"
        url = f"https://picsum.photos/seed/{seed}/512/512"
        req = Request(url, headers={"User-Agent": "tryonke-seeder/1.0"})
        try:
            with urlopen(req, timeout=15) as resp:
                content = resp.read()
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            logger.warning(
                "Image fetch failed for product %s (%s); attaching no image", product.pk, exc,
            )
            self.stdout.write(
                self.style.WARNING(
                    f"    image fetch failed for {product.name!r}: {exc} — product saved without image"
                )
            )
            return

        try:
            ProductImage.objects.create(
                product=product,
                image=ContentFile(content, name=f"{seed}.jpg"),
                is_main=True,
            )
        except Exception as exc:
            # Storage backend (Cloudinary) failure shouldn't abort the
            # batch — surface and continue.
            logger.warning(
                "ProductImage save failed for product %s (%s); skipping image", product.pk, exc,
            )
            self.stdout.write(
                self.style.WARNING(
                    f"    storage save failed for {product.name!r}: {exc} — product saved without image"
                )
            )
