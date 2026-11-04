from __future__ import annotations

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.audit.models import AuditAction
from apps.audit.services import record_audit

from .models import User, UserRole


class UserSerializer(serializers.ModelSerializer):
    role_label = serializers.CharField(source="get_role_display", read_only=True)
    is_locked = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "full_name",
            "email",
            "role",
            "role_label",
            "is_active",
            "must_change_password",
            "last_login_at",
            "last_login_ip",
            "is_locked",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "last_login_at",
            "last_login_ip",
            "is_locked",
            "created_at",
            "updated_at",
        ]


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    force_password_change = serializers.BooleanField(write_only=True, default=True)

    class Meta:
        model = User
        fields = [
            "username",
            "full_name",
            "email",
            "role",
            "password",
            "force_password_change",
            "is_active",
        ]

    def validate_username(self, value):
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError(
                "Le nom d'utilisateur doit contenir au moins 3 caractères."
            )
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Ce nom d'utilisateur existe déjà.")
        return value

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def create(self, validated_data):
        request = self.context.get("request")
        actor = getattr(request, "user", None)
        force_change = validated_data.pop("force_password_change", True)
        password = validated_data.pop("password")
        user = User.objects.create_user(
            password=password,
            must_change_password=force_change,
            created_by=actor if getattr(actor, "is_authenticated", False) else None,
            **validated_data,
        )
        record_audit(
            AuditAction.USER_CREATED,
            actor=actor,
            entity="User",
            entity_id=user.pk,
            description=f"Création de l'utilisateur {user.username} ({user.role})",
            metadata={"role": user.role, "force_password_change": force_change},
        )
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["full_name", "email", "role", "is_active", "must_change_password"]

    def validate(self, attrs):
        request = self.context.get("request")
        actor = getattr(request, "user", None)
        target: User = self.instance
        new_role = attrs.get("role", target.role)
        new_active = attrs.get("is_active", target.is_active)

        if actor and actor.pk == target.pk:
            if new_role != UserRole.ADMIN:
                raise serializers.ValidationError(
                    "Vous ne pouvez pas retirer votre propre rôle administrateur."
                )
            if not new_active:
                raise serializers.ValidationError(
                    "Vous ne pouvez pas désactiver votre propre compte."
                )
        if (
            target.role == UserRole.ADMIN
            and (new_role != UserRole.ADMIN or not new_active)
            and User.objects.filter(role=UserRole.ADMIN, is_active=True)
            .exclude(pk=target.pk)
            .count()
            == 0
        ):
            raise serializers.ValidationError(
                "Impossible : il doit rester au moins un administrateur actif."
            )
        return attrs

    def update(self, instance, validated_data):
        request = self.context.get("request")
        actor = getattr(request, "user", None)
        before = {
            "role": instance.role,
            "is_active": instance.is_active,
            "must_change_password": instance.must_change_password,
        }
        user = super().update(instance, validated_data)
        changes = {
            key: {"avant": before[key], "après": getattr(user, key)}
            for key in before
            if before[key] != getattr(user, key)
        }
        record_audit(
            AuditAction.USER_UPDATED,
            actor=actor,
            entity="User",
            entity_id=user.pk,
            description=f"Modification de l'utilisateur {user.username}",
            metadata={
                "champs": changes,
                "full_name": user.full_name,
                "email": user.email,
            },
        )
        return user


class PasswordResetSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    force_change = serializers.BooleanField(default=True)

    def validate_new_password(self, value):
        user = self.context.get("target_user")
        try:
            validate_password(value, user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    new_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    confirm_password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_current_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Le mot de passe actuel est incorrect.")
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Les deux mots de passe ne correspondent pas."}
            )
        user = self.context["request"].user
        if attrs["current_password"] == attrs["new_password"]:
            raise serializers.ValidationError(
                {"new_password": "Le nouveau mot de passe doit être différent de l'ancien."}
            )
        try:
            validate_password(attrs["new_password"], user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)}) from exc
        return attrs

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password", "password_changed_at", "updated_at"])
        record_audit(
            AuditAction.PASSWORD_CHANGED,
            actor=user,
            entity="User",
            entity_id=user.pk,
            description="Changement de mot de passe par l'utilisateur.",
        )
        return user
