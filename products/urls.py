from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductCategoryViewSet, ProductViewSet

router = DefaultRouter()
router.register(r'categories', ProductCategoryViewSet)
router.register(r'', ProductViewSet)

urlpatterns = [
    path('products/', include(router.urls)),
]
