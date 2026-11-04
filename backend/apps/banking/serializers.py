from __future__ import annotations

from rest_framework import serializers

from apps.core.utils import mask_account_number

from .models import BalanceSnapshot, ConnectionStatus, EcobankConfiguration, SyncLog


class EcobankConfigSerializer(serializers.ModelSerializer):
    """Admin-facing configuration.

    Secrets are write-only: they can be set but are NEVER returned. Only
    ``has_*`` flags and a masked account number are exposed.
    """

    secret_key = serializers.CharField(write_only=True, required=False, allow_blank=True)
    subscription_key = serializers.CharField(write_only=True, required=False, allow_blank=True)
    account_no = serializers.CharField(write_only=True, required=False, allow_blank=True)

    has_secret_key = serializers.BooleanField(read_only=True)
    has_subscription_key = serializers.BooleanField(read_only=True)
    has_account_no = serializers.BooleanField(read_only=True)
    connection_status = serializers.SerializerMethodField()
    connection_status_label = serializers.SerializerMethodField()
    is_configured = serializers.BooleanField(read_only=True)
    sandbox_simulation = serializers.BooleanField(read_only=True)

    class Meta:
        model = EcobankConfiguration
        fields = [
            "is_enabled",
            "environment",
            "base_url",
            "auth_path",
            "balance_path",
            "client_id",
            "affiliate_code",
            "source_code",
            "public_key",
            "ip_address",
            "secret_key",
            "subscription_key",
            "account_no",
            "account_name",
            "currency",
            "masked_account_no",
            "service_code",
            "token_request_type",
            "balance_request_type",
            "timeout_seconds",
            "sync_interval_minutes",
            "auto_sync_enabled",
            "sandbox_mode_enabled",
            "has_secret_key",
            "has_subscription_key",
            "has_account_no",
            "connection_status",
            "connection_status_label",
            "is_configured",
            "sandbox_simulation",
            "last_test_at",
            "last_test_status",
            "last_test_message",
            "last_sync_at",
            "last_sync_status",
            "last_sync_message",
            "updated_at",
        ]
        read_only_fields = [
            "masked_account_no",
            "account_name",
            "last_test_at",
            "last_test_status",
            "last_test_message",
            "last_sync_at",
            "last_sync_status",
            "last_sync_message",
            "updated_at",
        ]

    def get_connection_status(self, obj) -> str:
        return obj.connection_status()

    def get_connection_status_label(self, obj) -> str:
        return dict(ConnectionStatus.choices).get(obj.connection_status(), "")

    def validate_base_url(self, value):
        value = (value or "").strip().rstrip("/")
        if not value.startswith("https://"):
            raise serializers.ValidationError(
                "L'URL de l'API Ecobank doit utiliser HTTPS."
            )
        return value

    def validate_auth_path(self, value):
        value = (value or "").strip()
        if not value.startswith("/"):
            raise serializers.ValidationError("Le chemin doit commencer par « / ».")
        return value

    def validate_balance_path(self, value):
        value = (value or "").strip()
        if not value.startswith("/"):
            raise serializers.ValidationError("Le chemin doit commencer par « / ».")
        return value

    def validate_account_no(self, value):
        value = (value or "").strip()
        if value and not value.replace("-", "").isalnum():
            raise serializers.ValidationError(
                "Numéro de compte invalide (caractères alphanumériques uniquement)."
            )
        return value

    def validate_timeout_seconds(self, value):
        if not 5 <= value <= 120:
            raise serializers.ValidationError("Le délai doit être compris entre 5 et 120 secondes.")
        return value

    def validate_sync_interval_minutes(self, value):
        if not 1 <= value <= 1440:
            raise serializers.ValidationError("Intervalle attendu entre 1 et 1440 minutes.")
        return value

    def validate(self, attrs):
        instance = self.instance
        target_env = attrs.get("environment", getattr(instance, "environment", None))
        base_url = attrs.get("base_url")
        if target_env == "PRODUCTION" and base_url and "uat" in base_url.lower():
            raise serializers.ValidationError(
                {
                    "base_url": (
                        "Une URL UAT (sandbox) ne peut pas être utilisée en environnement "
                        "Production."
                    )
                }
            )
        return attrs

    def update(self, instance, validated_data):
        for secret_field in ("secret_key", "subscription_key", "account_no"):
            value = validated_data.pop(secret_field, None)
            if value:
                setattr(instance, secret_field, value)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if instance.account_no and not instance.masked_account_no:
            instance.masked_account_no = mask_account_number(instance.account_no)
        instance.save()
        return instance


class BalanceSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = BalanceSnapshot
        fields = [
            "id",
            "status",
            "source",
            "is_sandbox",
            "available_balance",
            "current_balance",
            "currency",
            "account_no_masked",
            "account_name",
            "account_status",
            "branch_code",
            "response_code",
            "fetched_at",
        ]
        read_only_fields = fields


class SyncLogSerializer(serializers.ModelSerializer):
    trigger_label = serializers.CharField(source="get_trigger_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    triggered_by_username = serializers.CharField(
        source="triggered_by.username", read_only=True, default=None
    )

    class Meta:
        model = SyncLog
        fields = [
            "id",
            "trigger",
            "trigger_label",
            "status",
            "status_label",
            "http_status",
            "response_code",
            "message",
            "duration_ms",
            "is_sandbox",
            "triggered_by_username",
            "created_at",
        ]
        read_only_fields = fields
