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
    