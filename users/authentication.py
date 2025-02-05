from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.conf import settings
import jwt
from .models import User
from datetime import datetime
import time

class KeycloakTokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            raise AuthenticationFailed('Authorization header missing')

        try:
            token = auth_header.split(' ')[1]
            decoded_token = jwt.decode(
                token,
                options={"verify_signature": False}
            )
            
            if decoded_token.get('exp'):
                if datetime.fromtimestamp(decoded_token.get('exp')) < datetime.now():
                    raise AuthenticationFailed('Token is expired')

            # Check if it's a service account/client credentials token
            if 'client_id' in decoded_token.get('azp', '').lower() or 'service-account' in decoded_token.get('preferred_username', '').lower():
                # Return only the token info without creating a user
                decoded_token['roles'] = {
                    'realm_roles': decoded_token.get('realm_access', {}).get('roles', []),
                    'resource_roles': decoded_token.get('resource_access', {}).get(settings.KEYCLOAK_CLIENT_ID, {}).get('roles', [])
                }
                return (None, decoded_token)
            
            # For regular user tokens, proceed with user creation/update
            user_data = {
                'keycloak_id': decoded_token.get('sub'),
                'username': decoded_token.get('preferred_username', ''),
                'email': decoded_token.get('email', f"{decoded_token.get('sub')}@placeholder.com"),
                'first_name': decoded_token.get('given_name', ''),
                'last_name': decoded_token.get('family_name', '')
            }

            user, _ = User.objects.get_or_create(
                keycloak_id=user_data['keycloak_id'],
                defaults=user_data
            )

            decoded_token['roles'] = {
                'realm_roles': decoded_token.get('realm_access', {}).get('roles', []),
                'resource_roles': decoded_token.get('resource_access', {}).get(settings.KEYCLOAK_CLIENT_ID, {}).get('roles', [])
            }
            
            return (user, decoded_token)
        except Exception as e:
            raise AuthenticationFailed(f'Invalid token: {str(e)}')
