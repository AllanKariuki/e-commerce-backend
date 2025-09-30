from rest_framework.permissions import BasePermission

class HasKeycloakRole(BasePermission):
    def __init__(self, required_role):
        self.required_role = required_role

    def has_permission(self, request, view):
        if not request.user:
            return False
            
        # Check in both realm and resource roles
        user_roles = request.user.get('roles', {})
        print('User roles:', user_roles)
        realm_roles = user_roles.get('realm_roles', [])
        print('Realm roles:', realm_roles)
        resource_roles = user_roles.get('resource_roles', [])
        
        return (self.required_role in realm_roles or 
                self.required_role in resource_roles)
class AdminOnly(BasePermission):
    def has_permission(self, request, view):
        if not request.user:
            return False
        user_roles = request.user.get('roles', {})
        realm_roles = user_roles.get('realm_roles', [])
        return 'admin' in realm_roles

class IsAuthenticatedOrGuest(BasePermission):
    """
    Allow both authenticated users and guests.
    Use for endpoints that should be accessible to everyone.
    """
    def has_permission(self, request, view):
        return request.user and (
            request.user.is_authenticated or 
            getattr(request.user, 'is_guest', False)
        )


class IsAuthenticatedUser(BasePermission):
    """
    Only allow authenticated Keycloak users, NOT guests.
    Use for endpoints that require a real user account.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated


class IsGuestUser(BasePermission):
    """
    Only allow guest users.
    Use for endpoints like "upgrade to full account".
    """
    def has_permission(self, request, view):
        return (
            request.user and 
            not request.user.is_authenticated and 
            getattr(request.user, 'is_guest', False)
        )


class IsAuthenticatedOrReadOnly(BasePermission):
    """
    Authenticated users can do anything.
    Guests can only read (GET, HEAD, OPTIONS).
    """
    def has_permission(self, request, view):
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        return request.user and request.user.is_authenticated