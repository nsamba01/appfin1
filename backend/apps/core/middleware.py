from __future__ import annotations

from django.conf import settings
from django.http import JsonResponse

PASSWORD_CHANGE_ALLOWED_PATHS = {
    "/api/auth/me/",
    "/api/auth/change-password/",
    "/api/auth/logout/",
    "/api/auth/refresh/",
    "/healthz",
}


class SecurityHeadersMiddleware:
    """Adds defensive HTTP headers (OWASP secure headers) to every response."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=(), payment=()"
        )
        response.headers.setdefault(
            "Cross-Origin-Opener-Policy", "same-origin"
        )
        response.headers.setdefault(
            "Cross-Origin-Resource-Policy", "same-site"
        )
        csp = "; ".join(
            [
                f"default-src {' '.join(settings.CSP_DEFAULT_SRC)}",
                f"script-src {' '.join(settings.CSP_SCRIPT_SRC)}",
                f"style-src {' '.join(settings.CSP_STYLE_SRC)}",
                f"img-src {' '.join(settings.CSP_IMG_SRC)}",
                f"font-src {' '.join(settings.CSP_FONT_SRC)}",
                f"connect-src {' '.join(settings.CSP_CONNECT_SRC)}",
                "frame-ancestors 'none'",
                "base-uri 'self'",
                "form-action 'self'",
                "object-src 'none'",
            ]
        )
        response.headers.setdefault("Content-Security-Policy", csp)
        if request.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response


class PasswordChangeEnforcementMiddleware:
    """Forces a password change on first login (or after an admin reset).

    While the flag is set, every API endpoint except the password-change flow is
    refused with 403 so the initial credentials cannot be used indefinitely.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        path = request.path
        if (
            user is not None
            and user.is_authenticated
            and getattr(user, "must_change_password", False)
            and path.startswith("/api/")
            and path not in PASSWORD_CHANGE_ALLOWED_PATHS
        ):
            return JsonResponse(
                {
                    "detail": "Vous devez changer votre mot de passe avant de continuer.",
                    "code": "password_change_required",
                },
                status=403,
            )
        return self.get_response(request)
