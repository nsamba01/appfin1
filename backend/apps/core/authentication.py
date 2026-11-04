from __future__ import annotations

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed


class PasswordAwareJWTAuthentication(JWTAuthentication):
    """Rejects access tokens issued before the last password change.

    This immediately invalidates existing sessions after a password reset or a
    password change, instead of waiting for the access token to expire.
    """

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        changed_at = getattr(user, "password_changed_at", None)
        if changed_at is not None:
            claim = validated_token.get("pwd_ts")
            invalid = False
            try:
                if claim is not None:
                    invalid = int(claim) != int(changed_at.timestamp() * 1_000_000)
                else:
                    iat = validated_token.get("iat")
                    invalid = iat is not None and float(iat) < changed_at.timestamp() - 1
            except (TypeError, ValueError):  # pragma: no cover
                invalid = False
            if invalid:
                raise AuthenticationFailed(
                    "Session invalidée : le mot de passe a été modifié. Reconnectez-vous.",
                    code="session_invalidated",
                )
        if not user.is_active:
            raise AuthenticationFailed("Compte désactivé.", code="inactive")
        return user
