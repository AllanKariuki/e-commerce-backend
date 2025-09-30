from django.utils.deprecation import MiddlewareMixin

class GuestCookieMiddleware(MiddlewareMixin):
    """
    Middleware to set guest_session_id cookie when a new guest is created.
    Must be placed AFTER AuthenticationMiddleware in MIDDLEWARE settings.
    """

    def process_response(self, request, response):
        # Check if the user is authenticated and is a guest that needs a cookie
        if hasattr(request, 'user') and hasattr(request.user, 'needs_cookie'):
            if request.user.needs_cookie:
                guest_id = getattr(request.user, 'guest_id', None)

                if guest_id:
                    # Set cookie with appropriate settings
                    response.set_cookie(
                        key='guest_session_id',
                        value=guest_id,
                        max_age=60 * 60 * 24 * 365, # 1 year
                        httponly=True, # Not accessible via JavaScript
                        secure=False, # HTTPS only (set to false if not using HTTPS)
                        samesite='Lax' # CSRF protection
                    )
        return response