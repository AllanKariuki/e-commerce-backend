from rest_framework.pagination import PageNumberPagination, LimitOffsetPagination
from rest_framework.response import Response


class BasePageNumberPagination(PageNumberPagination):
    page_size_query_param= 'page_size'
    max_page_size = 100

    def get_paginated_metadata(self):
        return {
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'page_size': self.get_page_size(self.request),
            'has_next': self.page.has_next(),
            'has_previous': self.page.has_previous(),
        }


class CustomPageNumberPagination(BasePageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    
    def get_paginated_response(self, data):
        return Response({
            'pagination': self.get_paginated_metadata(),
            'results': data
        })


class CustomLimitOffsetPagination(LimitOffsetPagination):
    page_size = 20
    limit_query_param = 'limit'
    offset_query_param = 'offset'
    max_page_size = 100


class ProductPagination(BasePageNumberPagination):
    """Custom pagination specifically for products"""
    page_size = 12  # Good for product grids (3x4, 4x3, etc.)
    page_size_query_param = 'page_size'
    max_page_size = 50
    
    def get_paginated_response(self, data):
        return Response({
            'pagination': self.get_paginated_metadata(),
            'products': data
        })