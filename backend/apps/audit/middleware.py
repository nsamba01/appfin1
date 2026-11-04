"""Thread-local access to the current request for audit logging."""
from __future__ import annotations

import threading

_local = threading.local()


def get_current_request():
    return getattr(_local, "request", None)


class AuditRequestMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _local.request = request
        try:
            response = self.get_response(request)
        finally:
            _local.request = None
        return response
