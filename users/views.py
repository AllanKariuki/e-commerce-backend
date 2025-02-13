from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from .authentication import KeycloakTokenAuthentication
from .custompermissions import HasKeycloakRole
from rest_framework import viewsets, status
from .models import User
from .serializers import UserSerializer


class UserViewset(viewsets.ViewSet):
    authentication_classes = [KeycloakTokenAuthentication]

    queryset = User.objects.all()
    def get_queryset(self):
        return User.objects.all()

    def list(self, request):
        queryset = self.get_queryset()
        serializer = UserSerializer(queryset, many=True)
        return Response(serializer.data)
    
    def create(self, request):
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
            return Response({'detail':serializer.data}, status=status.HTTP_200_OK)
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