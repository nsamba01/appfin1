from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit.models import AuditAction
from apps.audit.services import record_audit
from apps.core.models import ApplicationSettings
from apps.core.utils import client_ip
from apps.users.models import LoginAttempt, User, UserRole
from apps.users.serializers import ChangePasswordSerializer, UserSerializer

from .services import (
    issue_refresh_token,
    register_session,
    revoke_all_user_tokens,
    revoke_session,
)

logger = logging.getLogger("apps.authentication")


def _set_refresh_cookie(response: Response, refresh: RefreshToken) -> None:
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=str(refresh),
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        path=settings.REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        settings.REFRESH_COOKIE_NAME,
        path=settings.REFRESH_COOKIE_PATH,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
    )


def _user_payload(user: User) -> dict:
    settings_obj = ApplicationSettings.load()
    return {
        **UserSerializer(user).data,
        "permissions": {
            "can_manage_users": user.is_administrator,
            "can_manage_bank_config": user.is_administrator,
            "can_view_audit_logs": user.is_administrator,
            "can_manage_operations": True,
            "can_view_bank_data": True,
            "can_export": True,
        },
        "application": {
            "company_name": settings_obj.company_name,
            "currency": settings_obj.currency,
            "role": user.role,
        },
    }


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "login"

    def post(self, request):
        username = (request.data.get("username") or "").strip()
        password = request.data.get("password") or ""
        ip = client_ip(request)
        user_agent = (request.META.get("HTTP_USER_AGENT") or "")[:255]

        if not username or not password:
            return Response(
                {"detail": "Nom d'utilisateur et mot de passe requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.filter(username__iexact=username).first()

        def log_attempt(success: bool, reason: str = "", target=None):
            LoginAttempt.objects.create(
                username_attempted=username[:150],
                user=target,
                successful=success,
                ip_address=ip or None,
                user_agent=user_agent,
                reason=reason[:120],
            )

        if user is None:
            log_attempt(False, "unknown_username")
            record_audit(
                AuditAction.LOGIN_FAILED,
                entity="User",
                description=f"Tentative de connexion avec un identifiant inconnu: {username[:60]}",
                metadata={"ip": ip},
            )
            return Response(
                {"detail": "Identifiants invalides."}, status=status.HTTP_401_UNAUTHORIZED
            )

        if user.is_locked:
            log_attempt(False, "locked", user)
            record_audit(
                AuditAction.LOGIN_FAILED,
                actor=user,
                entity="User",
                entity_id=user.pk,
                description="Tentative de connexion sur un compte verrouillé.",
                metadata={"ip": ip},
            )
            return Response(
                {
                    "detail": (
                        "Compte temporairement verrouillé après plusieurs échecs. "
                        f"Réessayez après {timezone.localtime(user.locked_until):%H:%M}."
                    ),
                    "code": "account_locked",
                },
                status=status.HTTP_423_LOCKED,
            )

        if not user.is_active:
            log_attempt(False, "inactive", user)
            record_audit(
                AuditAction.LOGIN_FAILED,
                actor=user,
                entity="User",
                entity_id=user.pk,
                description="Tentative de connexion sur un compte désactivé.",
                metadata={"ip": ip},
            )
            return Response(
                {"detail": "Ce compte est désactivé. Contactez un administrateur."},
                status=status.HTTP_403_FORBIDDEN,
            )

        authenticated = authenticate(request=request, username=user.username, password=password)
        if authenticated is None:
            user.register_failed_login(
                settings.MAX_LOGIN_ATTEMPTS, settings.LOGIN_LOCKOUT_MINUTES
            )
            log_attempt(False, "bad_password", user)
            record_audit(
                AuditAction.LOGIN_FAILED,
                actor=user,
                entity="User",
                entity_id=user.pk,
                description="Mot de passe incorrect.",
                metadata={
                    "ip": ip,
                    "attempts": user.failed_login_attempts,
                },
            )
            remaining = max(settings.MAX_LOGIN_ATTEMPTS - user.failed_login_attempts, 0)
            detail = "Identifiants invalides."
            if user.is_locked:
                detail = "Trop de tentatives échouées. Le compte est temporairement verrouillé."
            elif remaining <= 2:
                detail = f"Identifiants invalides. {remaining} tentative(s) restante(s)."
            return Response(
                {"detail": detail, "attempts_remaining": remaining},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        authenticated.register_successful_login(ip)
        refresh = issue_refresh_token(authenticated)
        register_session(authenticated, refresh, ip, user_agent)
        log_attempt(True, "", authenticated)
        record_audit(
            AuditAction.LOGIN_SUCCESS,
            actor=authenticated,
            entity="User",
            entity_id=authenticated.pk,
            description="Connexion réussie.",
            metadata={"ip": ip, "role": authenticated.role},
        )

        response = Response(
            {
                "access": str(refresh.access_token),
                "user": _user_payload(authenticated),
            }
        )
        _set_refresh_cookie(response, refresh)
        return response


class RefreshView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        token = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if not token:
            return Response(
                {"detail": "Session expirée. Veuillez vous reconnecter.", "code": "no_session"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            refresh = RefreshToken(token)
        except TokenError:
            return Response(
                {"detail": "Session expirée. Veuillez vous reconnecter.", "code": "invalid_session"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user_id = refresh.get("user_id")
        user = User.objects.filter(pk=user_id, is_active=True).first()
        if user is None:
            revoke_session(refresh.get("jti"))
            response = Response(
                {"detail": "Compte indisponible.", "code": "inactive"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            _clear_refresh_cookie(response)
            return response

        old_jti = refresh.get("jti")
        if settings.SIMPLE_JWT["ROTATE_REFRESH_TOKENS"]:
            try:
                refresh.blacklist()
            except Exception:  # pragma: no cover
                pass
            new_refresh = issue_refresh_token(user)
            revoke_session(old_jti)
            register_session(
                user,
                new_refresh,
                client_ip(request),
                (request.META.get("HTTP_USER_AGENT") or "")[:255],
            )
        else:  # pragma: no cover - rotation is enabled by default
            new_refresh = refresh

        response = Response(
            {"access": str(new_refresh.access_token), "user": _user_payload(user)}
        )
        _set_refresh_cookie(response, new_refresh)
        return response


class LogoutView(APIView):
    permission_classes = [AllowAny]
    allow_password_change_pending = True

    def post(self, request):
        token = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if token:
            try:
                refresh = RefreshToken(token)
                revoke_session(refresh.get("jti"))
                refresh.blacklist()
            except TokenError:
                pass
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            record_audit(
                AuditAction.LOGOUT,
                actor=user,
                entity="User",
                entity_id=user.pk,
                description="Déconnexion.",
            )
        response = Response({"detail": "Déconnexion réussie."})
        _clear_refresh_cookie(response)
        return response


class MeView(APIView):
    allow_password_change_pending = True
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(_user_payload(request.user))


class ChangePasswordView(APIView):
    allow_password_change_pending = True
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        revoke_all_user_tokens(user)
        response = Response(
            {
                "detail": "Mot de passe modifié. Reconnectez-vous avec votre nouveau mot de passe.",
                "user": _user_payload(user),
            }
        )
        _clear_refresh_cookie(response)
        return response


class RolesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            [{"value": role.value, "label": role.label} for role in UserRole]
        )
