"""
Throttles for expensive product endpoints.

The visual-search endpoint fans out to paid third-party services on every
call (Cloudinary upload + Replicate CLIP embedding), so an un-throttled
anonymous endpoint is both a cost and an abuse risk. These scoped throttles
cap how often a single caller can trigger that pipeline.

Two classes are stacked on the view so both identity modes are covered:

  * ``VisualSearchUserThrottle`` — applies to authenticated SimpleJWT users,
    keyed by their user id (so the limit follows the account across IPs).
  * ``VisualSearchAnonThrottle`` — applies to everyone else (guests and true
    anonymous callers), keyed by client IP.

DRF's ``UserRateThrottle`` returns ``None`` (no throttle) for anonymous
requests and ``AnonRateThrottle`` returns ``None`` for authenticated ones,
so stacking both means exactly one bucket is consulted per request. Rates
are configured under ``DEFAULT_THROTTLE_RATES`` in settings.
"""

from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class VisualSearchAnonThrottle(AnonRateThrottle):
    """Per-IP cap for guests / anonymous callers hitting visual search."""

    scope = "visual_search_anon"


class VisualSearchUserThrottle(UserRateThrottle):
    """Per-user cap for authenticated callers hitting visual search."""

    scope = "visual_search_user"
