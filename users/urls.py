from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from .views import UserViewset, me, register


router = DefaultRouter()
router.register(r'users', UserViewset)


# SimpleJWT auth surface:
#   POST /api/auth/register   – create account, returns access+refresh
#   POST /api/auth/token      – login (email + password) -> access+refresh
#   POST /api/auth/token/refresh – exchange refresh for fresh access
#   POST /api/auth/token/verify  – cheap server-side token sanity check
#   GET  /api/auth/me         – current user
auth_urlpatterns = [
    path('register/', register, name='auth_register'),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('me/', me, name='auth_me'),
]

urlpatterns = [
    path('', include(router.urls)),
    path('auth/', include(auth_urlpatterns)),
]
