"""
Authentication classes for TryOn.ke.

There are two classes of interest here:

* `GuestOrJWTAuthentication` — the **current** default for the MVP. It
  validates a SimpleJWT bearer token if present, otherwise falls back to
  the guest-cookie flow so anonymous shoppers can still hit the API.

* `KeycloakTokenAuthentication` / `GuestOrKeycloakTokenAuthentication` —
  **legacy** classes kept for reference while we run on SimpleJWT. They
  trust unsigned JWTs (signature verification was disabled) and reach
  out to Keycloak, which we removed from the compose file on 2026-05-21
  to simplify boot. Do not wire these into REST_FRAMEWORK unless
  Keycloak is back in the stack.
"""

from datetime import datetime

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.utils.crypto import get_random_string
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

import jwt

from .models import GuestSession

User = get_user_model()


# ---------------------------------------------------------------------------
# Current (MVP) authentication
# ---------------------------------------------------------------------------


class GuestOrJWTAuthentication(BaseAuthentication):
    """
    DRF auth class that supports two identity modes:

      1. **Authenticated user** — request has `Authorization: Bearer <jwt>`
         where `<jwt>` is a SimpleJWT access token. Delegates to
         `rest_framework_simplejwt.authentication.JWTAuthentication` for
         signature + expiry verification; returns the resolved `User`.

      2. **Guest** — no/invalid Authorization header. Reuses an existing
         `guest_session_id` cookie or creates one and flags it so
         `GuestCookieMiddleware` sets the cookie on the response.

    Priority is **JWT first**, then guest. If a header is present but the
    token is invalid we raise `AuthenticationFailed` — failing closed
    matches what the old Keycloak class did and prevents a stale/forged
    token from silently downgrading to a guest session.
    """

    def __init__(self):
        # Reuse SimpleJWT's own implementation for the JWT half. Calling
        # `authenticate()` on it does header parsing + signature check.
        self._jwt = JWTAuthentication()

    def authenticate(self, request):
        auth_header = request.headers.get("Authorization", "")
        if auth_header and auth_header.startswith("Bearer "):
            return self._authenticate_jwt(request)
        return self._authenticate_guest(request)

    def authenticate_header(self, request):
        # WWW-Authenticate header on 401 responses.
        return 'Bearer realm="api"'

    # -- JWT branch ------------------------------------------------------

    def _authenticate_jwt(self, request):
        try:
            result = self._jwt.authenticate(request)
        except (InvalidToken, TokenError) as exc:
            raise AuthenticationFailed(str(exc))
        if result is None:
            # SimpleJWT returns None when the header wasn't a Bearer it
            # could parse. We already know it starts with "Bearer " so
            # this is effectively malformed.
            raise AuthenticationFailed("Invalid authorization header.")
        user, validated_token = result
        if not user.is_active:
            raise AuthenticationFailed("User account is disabled.")
        return (user, validated_token)

    # -- Guest branch ----------------------------------------------------

    def _authenticate_guest(self, request):
        guest_id = request.COOKIES.get("guest_session_id")
        if guest_id:
            try:
                guest_session = GuestSession.objects.get(session_id=guest_id)
                return (self._build_guest(guest_id, guest_session), None)
            except GuestSession.DoesNotExist:
                # Fall through and create a fresh one.
                pass

        new_id = get_random_string(32)
        guest_session = GuestSession.objects.create(session_id=new_id)
        guest_user = self._build_guest(new_id, guest_session)
        guest_user.needs_cookie = True
        return (guest_user, None)

    @staticmethod
    def _build_guest(guest_id, guest_session):
        guest_user = AnonymousUser()
        guest_user.guest_id = guest_id
        guest_user.guest_session = guest_session
        guest_user.is_guest = True
        return guest_user


# ---------------------------------------------------------------------------
# Legacy Keycloak classes — kept for reference, no longer wired in.
# ---------------------------------------------------------------------------


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
        guest_user.needs_cookie = True  # Flag for middleware to set cookie

        return (guest_user, None)
