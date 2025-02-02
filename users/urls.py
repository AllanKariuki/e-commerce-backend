# from .views import admin_only_view, user_view, UserViewset
from .views import UserViewset
from django.urls import path, include
from rest_framework.routers import DefaultRouter

router = DefaultRouter()

router.register(r'users', UserViewset)


urlpatterns = [
    # path('admin/', admin_only_view, name='admin_only'),
    # path('user/', user_view, name='user_view'),
    path('', include(router.urls)),
]