from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Q, Case, When
from .models import Product, ProductCategory, ProductImage
from django.db.models import Prefetch
from .serializers import ProductSerializer, ProductCategorySerializer
from .pagination import ProductPagination, CustomPageNumberPagination
from rest_framework.parsers import MultiPartParser, FormParser
from .redis_recent import log_view, get_recent_ids


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
        
