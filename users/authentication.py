from rest_framework.authentication import BaseAuthentication
from django_keycloak.services import KeycloakService
from rest_framework.exceptions import AuthenticationFailed
from django.conf import settings

class KeycloakTokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return None

        try:
            token = auth_header.split(' ')[1]
            keycloak_service = KeycloakService()
            user_info = keycloak_service.verify_token(token)
            
            # Extract roles from token
            realm_roles = user_info.get('realm_access', {}).get('roles', [])
            resource_roles = user_info.get('resource_access', {}).get(settings.KEYCLOAK_CLIENT_ID, {}).get('roles', [])
            
            # Add roles to user info for easy access
            user_info['roles'] = {
                'realm_roles': realm_roles,
                'resource_roles': resource_roles
            }
            
            return (user_info, None)
        except Exception as e:
            raise AuthenticationFailed('Invalid token')
