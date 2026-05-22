from django.contrib.auth import get_user_model
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import RegisterSerializer, UserSerializer


User = get_user_model()


class UserViewset(viewsets.ViewSet):
    """
    Admin/CRUD view over users. Read endpoints are open while we build
    out the UI; mutations require auth (SimpleJWT) — anonymous shoppers
    shouldn't be able to delete people.
    """

    queryset = User.objects.all()

    def get_permissions(self):
        # Reads stay open; writes need an authenticated user.
        if self.action in ('list', 'retrieve'):
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        return User.objects.all()

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
        queryset = self.get_queryset()
        try:
            user = queryset.get(pk=pk)
            serializer = UserSerializer(user)
            return Response({'detail': serializer.data}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({'detail': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

    def update(self, request, pk=None):
        queryset = self.get_queryset()
        try:
            user = queryset.get(pk=pk)
            serializer = UserSerializer(user, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response({'detail': 'User updated successfully'}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({'detail': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

    def destroy(self, request, pk=None):
        queryset = self.get_queryset()
        try:
            user = queryset.get(pk=pk)
            user.delete()
            return Response({'detail': 'User deleted successfully'}, status=status.HTTP_204_NO_CONTENT)
        except User.DoesNotExist:
            return Response({'detail': 'User not found'}, status=status.HTTP_404_NOT_FOUND)


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
