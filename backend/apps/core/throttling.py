from rest_framework.throttling import ScopedRateThrottle as DRFScopedRateThrottle


class ScopedRateThrottle(DRFScopedRateThrottle):
    """Scoped throttling that keys anonymous logins by IP and users by id."""

    def get_cache_key(self, request, view):
        scope = getattr(view, "throttle_scope", None)
        if not scope:
            return None
        if request.user and request.user.is_authenticated:
            ident = f"user:{request.user.pk}"
        else:
            ident = f"ip:{self.get_ident(request)}"
        return self.cache_format % {"scope": scope, "ident": ident}
