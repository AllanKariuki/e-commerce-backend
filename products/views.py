# from django.shortcuts import render
# from rest_framework import viewsets, status
# from rest_framework.response import Response
# from .models import Product, ProductCategory
# from .serializers import ProductSerializer, ProductCategorySerializer


# class ProductCategoryViewSet(viewsets.ModelViewSet):
#     queryset = ProductCategory.objects.all()
#     serializer_class = ProductCategorySerializer

# class ProductViewSet(viewsets.ModelViewSet):
#     queryset = Product.objects.all()
#     serializer_class = ProductSerializer

from rest_framework import viewsets
from django.db.models import Q
from .models import Product, ProductCategory
from .serializers import ProductSerializer, ProductCategorySerializer
from .pagination import ProductPagination, CustomPageNumberPagination


class ProductCategoryViewSet(viewsets.ModelViewSet):
    queryset = ProductCategory.objects.all()
    serializer_class = ProductCategorySerializer
    pagination_class = CustomPageNumberPagination

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
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
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

        # ORdering 
        ordering = self.request.query_params.get('ordering', None)
        if ordering is not None:
            # Allow ordering by name, price, units in stock and category
            allowed_orderings = ['name', '-name', 'price', '-price',
                                    'units_in_stock', '-units_in_stock',
                                    'category__name', '-category__name']
            if ordering in allowed_orderings:
                queryset = queryset.order_by(ordering)

        return queryset