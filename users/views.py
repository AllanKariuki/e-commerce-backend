from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from .authentication import KeycloakTokenAuthentication
from .custompermissions import HasKeycloakRole
from rest_framework import viewsets, status
from .models import User

# @api_view(['GET'])
# @authentication_classes([KeycloakTokenAuthentication])
# @permission_classes([HasKeycloakRole('admin')])
# def admin_only_view(request):
#     return Response({
#         'message': 'Admin access granted',
#         'user_info': request.user
#     })



# @api_view(['GET'])
# @authentication_classes([KeycloakTokenAuthentication])
# @permission_classes([user_permission])
# def user_view(request):
#     return Response({
#         'message': 'User access granted',
#         'user_info': request.user
#     })

# user_permission = HasKeycloakRole('user')

class UserViewset(viewsets.ViewSet):
    authentication_classes = [KeycloakTokenAuthentication]
    # permission_classes = [HasKeycloakRole('user')]
    # permission_classes = [user_permission]
    queryset = User.objects.all()
    def list(self, request):
       user_data = {
            'username': request.user.get('preferred_username'),
            'email': request.user.get('email'),
            'roles': request.user.get('roles'),
            'name': request.user.get('name')
        }
       return Response(user_data)