from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.conf import settings
import jwt
from jwt.exceptions import InvalidTokenError

class KeycloakTokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return None

        try:
            token = auth_header.split(' ')[1]
            # Decode and verify the token
            decoded_token = jwt.decode(
                token,
                options={"verify_signature": False}  # For development. In production, you should verify the signature
            )
            
            # Extract roles from token
            realm_roles = decoded_token.get('realm_access', {}).get('roles', [])
            resource_roles = decoded_token.get('resource_access', {}).get(settings.KEYCLOAK_CLIENT_ID, {}).get('roles', [])
            
            # Add roles to user info for easy access
            decoded_token['roles'] = {
                'realm_roles': realm_roles,
                'resource_roles': resource_roles
            }
            
            return (decoded_token, None)
        except InvalidTokenError:
            raise AuthenticationFailed('Invalid token')
