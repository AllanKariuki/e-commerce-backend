from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductCategoryViewSet, ProductViewSet, VisualSearchView

router = DefaultRouter()
router.register(r'categories', ProductCategoryViewSet)
router.register(r'products', ProductViewSet)

urlpatterns = [
    path('', include(router.urls)),
    # POST /api/search/visual — multipart image -> nearest products by
    # CLIP cosine distance. See VisualSearchView for the full pipeline.
    path('search/visual', VisualSearchView.as_view(), name='visual-search'),
]
