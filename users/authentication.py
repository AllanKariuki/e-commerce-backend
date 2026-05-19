from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.utils.crypto import get_random_string
from django.contrib.auth.models import AnonymousUser
from django.conf import settings
import jwt
from .models import User, GuestSession
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


class GuestOrKeycloakTokenAuthentication(BaseAuthentication):
    """
    Authentication class that supports both Keycloak JWT tokens and guest sessions.
    Priority: JWT token -> existing guest cookie -> create new guest session
    """

    def authenticate(self, request):
        # try to authenticate with keycloak token first
        auth_header = request.headers.get('Authorization')

        if auth_header and auth_header.startswith("Bearer "):
            try:
                token = auth_header.split(' ')[1]
                decoded_token = jwt.decode(
                    token,
                    options={"verify_signature": False}
                )
                
                #validate token expiration
                if decoded_token.get('exp'):
                    if datetime.fromtimestamp(decoded_token.get('exp')) < datetime.now():
                        raise AuthenticationFailed('Token is expired')

                # Handle service account/client credentials tokens
                if self._is_service_account(decoded_token):
                    decoded_token['roles'] = self._extract_roles(decoded_token)
                    return (None, decoded_token)
                
                
                # Handle regular user tokens
                user = self._get_or_create_user(decoded_token)
                decoded_token['roles'] = self._extract_roles(decoded_token)

                return (user, decoded_token)
            except jwt.DecodeError:
                raise AuthenticationFailed('Invalid token format.')
            except jwt.ExpiredSignatureError:
                raise AuthenticationFailed('Token has expired.')
            except Exception as e:
                raise AuthenticationFailed(f'Invalid token: {str(e)}')

        
        return self._authenticate_guest(request)

    def _is_service_account(self, decoded_token):
        """Check if token belongs to a service account"""
        azp = decoded_token.get('azp', '').lower()
        username = decoded_token.get('preferred_username', '').lower()
        return 'client_id' in azp or 'service-account' in username
    
    def _extract_roles(self, decoded_token):
        """Extract realm and resource roles from token"""
        return {
            'realm_roles': decoded_token.get('realm_access', {}).get('roles', []),
            'resource_roles': decoded_token.get('resource_access', {}).get(
                settings.KEYCLOAK_CLIENT_ID, {}
            ).get('roles', [])
        }
    
    def _get_or_create_user(self, decoded_token):
        """Create or update user from token data"""
        user_data = {
            'keycloak_id': decoded_token.get('sub'),
            'username': decoded_token.get('preferred_username', ''),
            'email': decoded_token.get('email', f"{decoded_token.get('sub')}@placeholder.com"),
            'first_name': decoded_token.get('given_name', ''),
            'last_name': decoded_token.get('family_name', '')
        }

        user, created = User.objects.get_or_create(
            keycloak_id=user_data['keycloak_id'],
            defaults=user_data
        )

        # Update user info if not created now
        if not created:
            for key, value in user_data.items():
                if key != 'keycloak_id' and value:
                    setattr(user, key, value)
            user.save(update_fields=['username', 'email', 'first_name', 'last_name'])

        return user
    
    def _authenticate_guest(self, request):
        """Authenticate or create a guest session"""
        guest_id = request.COOKIES.get("guest_session_id")

        if guest_id:
            # Try to find and existing guest session
            try:
                guest_session = GuestSession.objects.get(session_id=guest_id)
                guest_user = AnonymousUser()
                guest_user.guest_id = guest_id
                guest_user.guest_session = guest_session
                guest_user.is_guest = True
                return (guest_user, None)
            except GuestSession.DoesNotExist:
                pass
        
        # Create a new guest session
        guest_id = get_random_string(32)
        guest_session = GuestSession.objects.create(session_id=guest_id)

        guest_user = AnonymousUser()
        guest_user.guest_id = guest_id
        guest_user.guest_session = guest_session
        guest_user.is_guest = True
        guest_user.needs_cookie = True # Flag for middleware to set cookie
        
        return (guest_user, None)
    