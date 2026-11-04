from __future__ import annotations

import logging

from django.conf import settings
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.models import UserSession

logger = logging.getLogger("apps.authentication")


def stamp_password_claim(token: RefreshToken, user) -> None:
    """Embed the password version so a change invalidates older tokens."""
    changed_at = getattr(user, "password_changed_at", None)
    if changed_at is not None:
        token["pwd_ts"] = int(changed_at.timestamp() * 1_000_000)


def issue_refresh_token(user) -> RefreshToken:
    token = RefreshToken.for_user(user)
    stamp_password_claim(token, user)
    return token


def register_session(user, refresh_token: RefreshToken, ip: str | None, user_agent: str) -> None:
    try:
        UserSession.objects.create(
            user=user,
            jti=refresh_token["jti"],
            ip_address=ip or None,
            user_agent=(user_agent or "")[:255],
            expires_at=timezone.now() + settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"],
        )
    except Exception:  # pragma: no cover - never block a login on bookkeeping
        logger.exception("Unable to register user session")


def revoke_session(jti: str | None) -> None:
    if not jti:
        return
    UserSession.objects.filter(jti=jti, revoked_at__isnull=True).update(revoked_at=timezone.now())


def revoke_all_user_tokens(user) -> None:
    """Invalidate every outstanding refresh token and session (password change)."""
    now = timezone.now()
    UserSession.objects.filter(user=user, revoked_at__isnull=True).update(revoked_at=now)
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)
