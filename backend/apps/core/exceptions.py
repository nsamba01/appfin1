import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger("apps.core.exceptions")


def api_exception_handler(exc, context):
    """Normalise API errors and never leak internal details in production."""
    response = drf_exception_handler(exc, context)
    if response is not None:
        data = response.data
        if isinstance(data, dict) and "detail" in data and len(data) == 1:
            data = {"detail": str(data["detail"])}
            response.data = data
        return response

    logger.exception("Unhandled API exception", exc_info=exc)
    return Response(
        {"detail": "Une erreur interne est survenue. Veuillez réessayer."},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
