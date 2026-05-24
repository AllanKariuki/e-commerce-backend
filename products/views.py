import logging
import time
from io import BytesIO

from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.views import APIView
from django.db.models import Q, Case, When
from .models import Product, ProductCategory, ProductImage, SearchQuery
from django.db.models import Prefetch
from .serializers import ProductSerializer, ProductCategorySerializer
from .pagination import ProductPagination, CustomPageNumberPagination
from rest_framework.parsers import MultiPartParser, FormParser
from .redis_recent import log_view, get_recent_ids

logger = logging.getLogger(__name__)


class ProductCategoryViewSet(viewsets.ModelViewSet):
    queryset = ProductCategory.objects.all()
    serializer_class = ProductCategorySerializer
    # pagination_class = CustomPageNumberPagination

    def get_queryset(self):

        queryset = ProductCategory.objects.all()

        # Search by name
        name = self.request.query_params.get("name", None)
        if name is not None:
            queryset = queryset.filter(name__icontains=name)

        # search by description
        search = self.request.query_params.get('search', None)
        if search is not None:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(description__icontains=search)
            )

        return queryset

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().prefetch_related(
        Prefetch('images', queryset=ProductImage.objects.order_by('-is_main'))
    )
    serializer_class = ProductSerializer
    parser_classes = (MultiPartParser, FormParser)
    pagination_class = ProductPagination  # Custom pagination for products

    def get_queryset(self):
        queryset = Product.objects.all()

        # filter by ProductCategory
        category = self.request.query_params.get('category', None)
        if category is not None:
            queryset = queryset.filter(category_id=category)

        # Filter by catefory name
        category_name = self.request.query_params.get('category_name', None)
        if category_name is not None:
            queryset = queryset.filter(category__name__icontains=category_name)

        # Price range filtering
        min_price = self.request.query_params.get('min_price', None)
        if min_price is not None:
            try:
                queryset = queryset.filter(price__gte=float(min_price))
            except ValueError:
                pass

        max_price = self.request.query_params.get('max_price', None)
        if max_price is not None:
            try:
                queryset = queryset.filter(price__lte=float(max_price))
            except ValueError:
                pass
        
        # Filter by stock availability
        in_stock = self.request.query_params.get('in_stock', None)
        if in_stock is not None:
            if in_stock.lower() in ['true', '1', 'yes']:
                queryset = queryset.filter(units_in_stock__gt=0)
            elif in_stock.lower() in ['false', '0', 'no']:
                queryset = queryset.filter(units_in_stock=0)

        # General search across multiple fields
        search = self.request.query_params.get('search', None)
        if search is not None:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(category__name__icontains=search)
            )

        # Ordering
        ordering = self.request.query_params.get('ordering', None)
        if ordering is not None:
            # Allow ordering by name, price, units in stock and category
            allowed_orderings = ['name', '-name', 'price', '-price',
                                    'units_in_stock', '-units_in_stock',
                                    'category__name', '-category__name']
            if ordering in allowed_orderings:
                queryset = queryset.order_by(ordering)
        
        # Colors 
        color = self.request.query_params.get('color', None)
        if color is not None:
            queryset = queryset.filter(colors__contains=[color])
        
        # Sizes
        size = self.request.query_params.get('size', None)
        if size is not None:
            queryset = queryset.filter(sizes__contains=[size])

        return queryset
    
    def retrieve(self, request, *args, **kwargs):
        """ Override retrieve to log product view """
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        # Determine user identifier (user id for auth's users, or cookies or session ids for guests)
        user_identifier = self._get_user_identifier(request)
        # Log to redis
        try:
            log_view(user_identifier, instance.id)
        except Exception as e:
            print(f"Error logging view for user {user_identifier}: {e}")
            pass  # fail silently on logging errors
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="recent")
    def recent(self, request):
        """
        GET /products/recent/ -> return products for this user
        """
        user_identifier = self._get_user_identifier(request)
        ids = get_recent_ids(user_identifier, limit=20)
        print(f"Product ids from redis for {user_identifier}: {ids}")

        if not ids:
            return Response([])
        
        # Fetch products from DB preserving the order returned by Redis
        preserved = Case(*[When(id=pid, then=pos) for pos, pid in enumerate(ids)])
        product_qs = Product.objects.filter(id__in=ids).order_by(preserved)

        serializer = self.get_serializer(product_qs, many=True)
        return Response(serializer.data)
    
    def _get_user_identifier(self, request):
        if request.user and request.user.is_authenticated:
            return f"user:{request.user.id}"

        guest_cookie = request.COOKIES.get("guest_session_id")
        if guest_cookie:
            return f"guest:{guest_cookie}"


# ---------------------------------------------------------------------------
# Visual search
# ---------------------------------------------------------------------------

# Hard caps on what we'll accept from a client. Tuned for selfies / product
# photos taken on a phone; bigger uploads get rejected before we waste time
# decoding and shipping bytes to Cloudinary.
_MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # 8 MB
_THUMBNAIL_DIM = 256                 # px, longest edge — matches the build plan
_DEFAULT_RESULT_LIMIT = 24
_MAX_RESULT_LIMIT = 50


class VisualSearchView(APIView):
    """
    POST /api/search/visual

    Multipart upload (`image=<file>`) → returns the 24 nearest products
    by CLIP cosine distance.

    Pipeline (synchronous; aim is ~2-4s end-to-end on a Kenya 4G link):
      1. Validate + Pillow-open the uploaded file.
      2. Resize so the longest edge is 256px (saves Cloudinary storage
         and Replicate processing time without losing visual signal).
      3. Upload the resized JPEG to Cloudinary under `search_queries/`
         so Replicate has a publicly-fetchable URL.
      4. Call the shared `embed_image_url` helper (same Replicate
         CLIP model used to embed products at ingest time).
      5. Cosine-search the `Product.embedding` column ordered by
         `CosineDistance(embedding, query_vector)`, filtering rows
         whose embedding hasn't been populated yet.
      6. Serialize the top N products + distance and return them
         alongside metadata about the query (Cloudinary URL, latency).

    Anonymous access is intentional — rate limiting will be layered on
    in the Phase 1 rate-limit task. Every call is logged as a
    ``SearchQuery`` row (image URL, top result IDs, latency, who) so
    we can do relevance tuning later.
    """

    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        started = time.perf_counter()

        image_file = request.FILES.get("image")
        if image_file is None:
            return Response(
                {"detail": "Missing required field 'image'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if image_file.size and image_file.size > _MAX_UPLOAD_BYTES:
            return Response(
                {
                    "detail": (
                        f"Image too large ({image_file.size} bytes). "
                        f"Max is {_MAX_UPLOAD_BYTES} bytes."
                    ),
                },
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        # Optional `limit` query param so the frontend can grab a smaller
        # grid on mobile without us round-tripping more than needed.
        try:
            limit = int(request.query_params.get("limit", _DEFAULT_RESULT_LIMIT))
        except (TypeError, ValueError):
            limit = _DEFAULT_RESULT_LIMIT
        limit = max(1, min(limit, _MAX_RESULT_LIMIT))

        # 1+2: validate + resize via Pillow.
        try:
            thumb_buf = self._resize_to_thumbnail(image_file)
        except _InvalidImage as exc:
            return Response(
                {"detail": f"Uploaded file is not a valid image: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 3: upload to Cloudinary.
        try:
            query_image_url = self._upload_to_cloudinary(thumb_buf)
        except _CloudinaryUploadFailed as exc:
            logger.exception("Cloudinary upload failed for visual search")
            return Response(
                {"detail": f"Image upload failed: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # 4: embed via Replicate (shared with the Celery embed task).
        from products.tasks import embed_image_url  # local import keeps app loading fast

        vector = embed_image_url(query_image_url)
        if vector is None:
            return Response(
                {
                    "detail": (
                        "Could not compute an embedding for this image. "
                        "Replicate may be misconfigured or unreachable."
                    ),
                    "query_image_url": query_image_url,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # 5: pgvector cosine search.
        try:
            from pgvector.django import CosineDistance
        except ImportError:
            logger.error("pgvector not installed; cannot run visual search")
            return Response(
                {"detail": "Visual search backend not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        products_qs = (
            Product.objects.filter(embedding__isnull=False)
            .annotate(distance=CosineDistance("embedding", vector))
            .order_by("distance")
            .prefetch_related(
                Prefetch("images", queryset=ProductImage.objects.order_by("-is_main")),
            )[:limit]
        )
        products = list(products_qs)

        # 6: serialize.
        serialized = ProductSerializer(
            products, many=True, context={"request": request},
        ).data
        # CosineDistance returns a float in [0, 2] (0 = identical, 2 = opposite).
        for item, product in zip(serialized, products):
            item["distance"] = float(getattr(product, "distance", 0.0))

        latency_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "visual search: returned %d products in %dms (limit=%d)",
            len(products), latency_ms, limit,
        )

        # Persist the query for later relevance tuning. Failures here
        # must NEVER break the response — the user already got their
        # results; a bad row in our analytics table is our problem,
        # not theirs.
        self._log_search_query(
            request=request,
            image_url=query_image_url,
            products=products,
            latency_ms=latency_ms,
        )

        return Response(
            {
                "query": {
                    "image_url": query_image_url,
                    "embedding_dim": len(vector),
                    "latency_ms": latency_ms,
                },
                "count": len(products),
                "results": serialized,
            },
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _log_search_query(*, request, image_url, products, latency_ms):
        """Insert a ``SearchQuery`` row for this call.

        Best-effort: swallows any exception so that a DB or schema
        hiccup can't fail the visual-search response after the user
        has already paid the Replicate latency.
        """
        try:
            user = (
                request.user
                if getattr(request, "user", None) and request.user.is_authenticated
                else None
            )
            session_key = ''
            if user is None:
                # Match the guest-cookie convention used by ProductViewSet.
                session_key = request.COOKIES.get("guest_session_id", "") or ""

            SearchQuery.objects.create(
                image_url=image_url,
                top_result_ids=[p.id for p in products],
                latency_ms=latency_ms,
                result_count=len(products),
                user=user,
                session_key=session_key[:128],
            )
        except Exception:  # noqa: BLE001 — analytics must not break the response
            logger.exception("Failed to log SearchQuery row")

    # ---- helpers --------------------------------------------------------

    @staticmethod
    def _resize_to_thumbnail(image_file) -> BytesIO:
        """Return a JPEG BytesIO whose longest edge is `_THUMBNAIL_DIM` px.

        Raises `_InvalidImage` if Pillow can't decode the upload.
        """
        try:
            from PIL import Image, UnidentifiedImageError
        except ImportError as exc:  # pragma: no cover — pillow is in requirements
            raise _InvalidImage(f"Pillow unavailable: {exc}") from exc

        try:
            img = Image.open(image_file)
            img.load()
        except (UnidentifiedImageError, OSError) as exc:
            raise _InvalidImage(str(exc)) from exc

        # JPEG can't carry alpha. Convert eagerly so palette / RGBA PNGs
        # round-trip cleanly to the encoder below.
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        elif img.mode == "L":
            img = img.convert("RGB")

        img.thumbnail((_THUMBNAIL_DIM, _THUMBNAIL_DIM), Image.LANCZOS)

        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        buf.seek(0)
        return buf

    @staticmethod
    def _upload_to_cloudinary(buf: BytesIO) -> str:
        """Upload `buf` to Cloudinary and return its secure URL.

        Cloudinary's global config is set in settings.py, so we don't need
        to thread credentials through here.
        """
        try:
            import cloudinary.uploader  # type: ignore
        except ImportError as exc:  # pragma: no cover — cloudinary is in requirements
            raise _CloudinaryUploadFailed(f"cloudinary package unavailable: {exc}") from exc

        try:
            result = cloudinary.uploader.upload(
                buf,
                folder="search_queries",
                resource_type="image",
                # `unique_filename` is default-True so we never collide
                # across concurrent searches. `overwrite=False` keeps any
                # accidental same-name from clobbering.
                overwrite=False,
                # Strip ICC / EXIF — selfies often carry GPS metadata we
                # have no business persisting.
                invalidate=True,
            )
        except Exception as exc:  # cloudinary raises a variety of error classes
            raise _CloudinaryUploadFailed(str(exc)) from exc

        url = result.get("secure_url") or result.get("url")
        if not url:
            raise _CloudinaryUploadFailed("Cloudinary response missing image URL")
        return url


class _InvalidImage(Exception):
    """Raised when the uploaded file can't be opened by Pillow."""


class _CloudinaryUploadFailed(Exception):
    """Raised when Cloudinary refuses or errors during upload."""

