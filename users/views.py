from django.contrib.auth import get_user_model
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import RegisterSerializer, UserSerializer


User = get_user_model()


class UserViewset(viewsets.ViewSet):
    """
    CRUD view over user records, which expose PII (email, phone). Access is
    locked down per action:

      * ``list`` / ``create`` — staff only. Listing every user (with their
        email + phone) or minting accounts out-of-band is an admin task; the
        public signup flow is ``POST /api/auth/register``.
      * ``retrieve`` / ``update`` / ``destroy`` — the authenticated owner of
        the record, or any staff user. A logged-in shopper can read and edit
        their own profile but cannot touch anyone else's.

    Guests (anonymous + guest-cookie sessions) are rejected from every action
    by ``IsAuthenticated``; there is no longer any unauthenticated read path.
    """

    queryset = User.objects.all()

    def get_permissions(self):
        # Listing all users / admin-side creation is staff-only.
        if self.action in ('list', 'create'):
            return [IsAdminUser()]
        # retrieve / update / destroy: must be logged in; object-level
        # ownership is then enforced per-request in `_get_user_or_deny`.
        return [IsAuthenticated()]

    def get_queryset(self):
        return User.objects.all()

    def _get_user_or_deny(self, request, pk):
        """
        Fetch the target user and enforce object-level authorization.

        Returns ``(user, None)`` when the caller may act on the record, or
        ``(None, response)`` with a 404/403 to return otherwise. Staff may
        act on any record; everyone else only on their own. We return 404
        (not 403) for "exists but not yours" so the endpoint doesn't leak
        which user ids are real to a non-owner.
        """
        try:
            user = self.get_queryset().get(pk=pk)
        except User.DoesNotExist:
            return None, Response(
                {'detail': 'User not found'}, status=status.HTTP_404_NOT_FOUND
            )

        if not (request.user.is_staff or user.pk == request.user.pk):
            return None, Response(
                {'detail': 'User not found'}, status=status.HTTP_404_NOT_FOUND
            )
        return user, None

    def list(self, request):
        queryset = self.get_queryset()
        serializer = UserSerializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request):
        # Keep this endpoint for admin-side user creation. The public
        # signup flow lives at /api/auth/register and goes through
        # `RegisterSerializer` so a password is required + hashed.
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def retrieve(self, request, pk=None):
        user, denied = self._get_user_or_deny(request, pk)
        if denied is not None:
            return denied
        serializer = UserSerializer(user)
        return Response({'detail': serializer.data}, status=status.HTTP_200_OK)

    def update(self, request, pk=None):
        user, denied = self._get_user_or_deny(request, pk)
        if denied is not None:
            return denied
        serializer = UserSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'detail': 'User updated successfully'}, status=status.HTTP_200_OK)

    def destroy(self, request, pk=None):
        user, denied = self._get_user_or_deny(request, pk)
        if denied is not None:
            return denied
        user.delete()
        return Response({'detail': 'User deleted successfully'}, status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """
    Public signup. On success returns the new user record plus a fresh
    access+refresh token pair so the frontend can authenticate the
    user immediately without a second round-trip to /api/auth/token.
    """
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()

    refresh = RefreshToken.for_user(user)
    return Response(
        {
            'user': UserSerializer(user).data,
            'tokens': {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            },
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    """Convenience endpoint — return the currently-authenticated user."""
    return Response(UserSerializer(request.user).data)
