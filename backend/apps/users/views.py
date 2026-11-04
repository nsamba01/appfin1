from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditAction
from apps.audit.services import record_audit
from apps.core.models import ApplicationSettings
from apps.core.permissions import IsAdministrator
from apps.core.serializers import ApplicationSettingsSerializer
from apps.users.models import User, UserRole
from apps.users.serializers import (
    PasswordResetSerializer,
    UserCreateSerializer,
    UserSerializer,
    UserUpdateSerializer,
)


class AdminUserViewSet(viewsets.ModelViewSet):
    """User management — administrators only."""

    permission_classes = [IsAdministrator]
    queryset = User.objects.all().order_by("username")
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]
    search_fields = ["username", "full_name", "email"]
    filterset_fields = ["role", "is_active"]

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        if self.action in {"update", "partial_update"}:
            return UserUpdateSerializer
        return UserSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if search := params.get("search"):
            from django.db.models import Q

            qs = qs.filter(
                Q(username__icontains=search)
                | Q(full_name__icontains=search)
                | Q(email__icontains=search)
            )
        if role := params.get("role"):
            qs = qs.filter(role=role)
        if params.get("is_active") in {"true", "false"}:
            qs = qs.filter(is_active=params["is_active"] == "true")
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data)

    def destroy(self, request, *args, **kwargs):
        """Accounts are preserved: deletion means deactivation (audit-safe)."""
        instance = self.get_object()
        if instance.pk == request.user.pk:
            return Response(
                {"detail": "Vous ne pouvez pas désactiver votre propre compte."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if (
            instance.role == UserRole.ADMIN
            and not User.objects.filter(role=UserRole.ADMIN, is_active=True)
            .exclude(pk=instance.pk)
            .exists()
        ):
            return Response(
                {"detail": "Impossible : il doit rester au moins un administrateur actif."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])
        record_audit(
            AuditAction.USER_DEACTIVATED,
            entity="User",
            entity_id=instance.pk,
            description=f"Désactivation du compte {instance.username}",
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="password")
    def reset_password(self, request, pk=None):
        target = self.get_object()
        serializer = PasswordResetSerializer(
            data=request.data, context={"request": request, "target_user": target}
        )
        serializer.is_valid(raise_exception=True)
        new_password = serializer.validated_data["new_password"]
        force_change = serializer.validated_data.get("force_change", True)
        with transaction.atomic():
            target.set_password(new_password)
            target.must_change_password = force_change
            target.failed_login_attempts = 0
            target.locked_until = None
            target.save(
                update_fields=[
                    "password",
                    "must_change_password",
                    "failed_login_attempts",
                    "locked_until",
                    "password_changed_at",
                    "updated_at",
                ]
            )
            record_audit(
                AuditAction.PASSWORD_RESET,
                entity="User",
                entity_id=target.pk,
                description=f"Réinitialisation du mot de passe de {target.username}",
                metadata={"force_change": force_change},
            )
        return Response({"detail": "Mot de passe réinitialisé avec succès."})

    @action(detail=True, methods=["post"], url_path="toggle-active")
    def toggle_active(self, request, pk=None):
        target = self.get_object()
        if target.pk == request.user.pk:
            return Response(
                {"detail": "Vous ne pouvez pas modifier l'état de votre propre compte."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        activate = not target.is_active
        if (
            not activate
            and target.role == UserRole.ADMIN
            and not User.objects.filter(role=UserRole.ADMIN, is_active=True)
            .exclude(pk=target.pk)
            .exists()
        ):
            return Response(
                {"detail": "Impossible : il doit rester au moins un administrateur actif."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        target.is_active = activate
        target.failed_login_attempts = 0
        target.locked_until = None
        target.save(update_fields=["is_active", "failed_login_attempts", "locked_until", "updated_at"])
        record_audit(
            AuditAction.USER_ACTIVATED if activate else AuditAction.USER_DEACTIVATED,
            entity="User",
            entity_id=target.pk,
            description=f"{'Activation' if activate else 'Désactivation'} du compte {target.username}",
        )
        return Response(UserSerializer(target).data)

    @action(detail=True, methods=["post"], url_path="unlock")
    def unlock(self, request, pk=None):
        target = self.get_object()
        target.failed_login_attempts = 0
        target.locked_until = None
        target.save(update_fields=["failed_login_attempts", "locked_until", "updated_at"])
        record_audit(
            AuditAction.USER_UPDATED,
            entity="User",
            entity_id=target.pk,
            description=f"Déverrouillage du compte {target.username}",
        )
        return Response(UserSerializer(target).data)


class ApplicationSettingsView(APIView):
    permission_classes = [IsAdministrator]

    def get(self, request):
        settings_obj = ApplicationSettings.load()
        return Response(ApplicationSettingsSerializer(settings_obj).data)

    def patch(self, request):
        settings_obj = ApplicationSettings.load()
        serializer = ApplicationSettingsSerializer(settings_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        record_audit(
            AuditAction.SETTINGS_UPDATED,
            entity="ApplicationSettings",
            entity_id=1,
            description="Mise à jour des paramètres généraux.",
            metadata={"champs": list(serializer.validated_data.keys())},
        )
        return Response(serializer.data)

    def put(self, request):
        return self.patch(request)
