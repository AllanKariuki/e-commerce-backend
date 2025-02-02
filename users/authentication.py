from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.conf import settings
import jwt
from jwt.exceptions import InvalidTokenError
from .models import User

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

            # Extract user info from the token
            keycloak_id = decoded_token.get('sub')
            username = decoded_token.get('preferred_username')
            email = decoded_token.get('email')
            first_name = decoded_token.get('first_name')
            last_name = decoded_token.get('lastname')
            phone = decoded_token.get('phone')
            
            user, created = User.objects.get_or_create(
                keycloak_id=keycloak_id,
                defaults={
                    'username': username,
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'phone': phone
                }
            )

            # Update user info if has changed
            if not created:
                user.username = username
                user.email = email
                user.first_name = first_name
                user.last_name = last_name
                user.phone = phone
                user.save()

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
