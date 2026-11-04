from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.encryption import decrypt_str, encrypt_str
from apps.core.models import SingletonModel, TimeStampedModel
from apps.core.utils import mask_account_number


class BankEnvironment(models.TextChoices):
    SANDBOX = "SANDBOX", "Sandbox (UAT)"
    PRODUCTION = "PRODUCTION", "Production"


class ConnectionStatus(models.TextChoices):
    NOT_CONFIGURED = "NOT_CONFIGURED", "Non configuré"
    CONFIGURED = "CONFIGURED", "Configuré (non testé)"
    CONNECTED = "CONNECTED", "Connecté"
    ERROR = "ERROR", "Erreur de connexion"
    SANDBOX = "SANDBOX", "Mode sandbox (simulation)"


class SyncStatus(models.TextChoices):
    SUCCESS = "SUCCESS", "Succès"
    FAILED = "FAILED", "Échec"
    RUNNING = "RUNNING", "En cours"
    SKIPPED = "SKIPPED", "Ignoré"


class SyncTrigger(models.TextChoices):
    MANUAL = "MANUAL", "Manuelle"
    SCHEDULED = "SCHEDULED", "Planifiée"
    TEST = "TEST", "Test de connexion"


class EcobankConfiguration(SingletonModel, TimeStampedModel):
    """Administrator-managed Ecobank API configuration.

    Secrets are stored encrypted (Fernet) and are never returned by the API.
    """

    is_enabled = models.BooleanField(default=False)
    environment = models.CharField(
        max_length=16, choices=BankEnvironment.choices, default=BankEnvironment.SANDBOX
    )

    base_url = models.URLField(
        max_length=255, default=getattr(settings, "ECOBANK_DEFAULT_BASE_URL", "")
    )
    auth_path = models.CharField(
        max_length=255,
        default=getattr(settings, "ECOBANK_DEFAULT_AUTH_PATH", ""),
    )
    balance_path = models.CharField(
        max_length=255,
        default=getattr(settings, "ECOBANK_DEFAULT_BALANCE_PATH", ""),
    )

    client_id = models.CharField(max_length=120, blank=True, default="")
    affiliate_code = models.CharField(max_length=16, blank=True, default="")
    source_code = models.CharField(max_length=64, blank=True, default="")
    public_key = models.CharField(max_length=255, blank=True, default="")
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    secret_key_encrypted = models.TextField(blank=True, default="")
    subscription_key_encrypted = models.TextField(blank=True, default="")
    account_no_encrypted = models.TextField(blank=True, default="")

    masked_account_no = models.CharField(max_length=40, blank=True, default="")
    account_name = models.CharField(max_length=150, blank=True, default="")
    currency = models.CharField(max_length=8, blank=True, default="")

    service_code = models.CharField(max_length=32, blank=True, default="ACCOUNT_SERVICE")
    token_request_type = models.CharField(max_length=48, blank=True, default="GET_API_TOKEN")
    balance_request_type = models.CharField(
        max_length=48, blank=True, default="GET_ACCOUNT_BALANCE"
    )

    timeout_seconds = models.PositiveSmallIntegerField(default=30)
    sync_interval_minutes = models.PositiveSmallIntegerField(default=30)
    auto_sync_enabled = models.BooleanField(default=True)

    # Explicit, opt-in demonstration mode. Never presented as a real bank balance.
    sandbox_mode_enabled = models.BooleanField(
        default=False,
        help_text=(
            "Mode démonstration sandbox : produit un solde simulé clairement identifié. "
            "À n'activer que sans accès API réel."
        ),
    )

    last_test_at = models.DateTimeField(null=True, blank=True)
    last_test_status = models.CharField(
        max_length=16, choices=ConnectionStatus.choices, blank=True, default=""
    )
    last_test_message = models.CharField(max_length=500, blank=True, default="")

    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_sync_status = models.CharField(max_length=16, choices=SyncStatus.choices, blank=True, default="")
    last_sync_message = models.CharField(max_length=500, blank=True, default="")

    configured_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        verbose_name = "configuration Ecobank"
        verbose_name_plural = "configuration Ecobank"

    def __str__(self) -> str:  # pragma: no cover
        return f"Ecobank ({self.get_environment_display()})"

    # -- secret accessors --------------------------------------------------
    @property
    def secret_key(self) -> str:
        return decrypt_str(self.secret_key_encrypted)

    @secret_key.setter
    def secret_key(self, value: str) -> None:
        self.secret_key_encrypted = encrypt_str(value)

    @property
    def subscription_key(self) -> str:
        return decrypt_str(self.subscription_key_encrypted)

    @subscription_key.setter
    def subscription_key(self, value: str) -> None:
        self.subscription_key_encrypted = encrypt_str(value)

    @property
    def account_no(self) -> str:
        return decrypt_str(self.account_no_encrypted)

    @account_no.setter
    def account_no(self, value: str) -> None:
        self.account_no_encrypted = encrypt_str(value)
        self.masked_account_no = mask_account_number(value) if value else ""

    @property
    def has_secret_key(self) -> bool:
        return bool(self.secret_key_encrypted)

    @property
    def has_subscription_key(self) -> bool:
        return bool(self.subscription_key_encrypted)

    @property
    def has_account_no(self) -> bool:
        return bool(self.account_no_encrypted)

    @property
    def has_credentials(self) -> bool:
        return all(
            [
                self.base_url,
                self.auth_path,
                self.balance_path,
                self.client_id,
                self.affiliate_code,
                self.source_code,
                self.public_key,
                self.secret_key_encrypted,
                self.subscription_key_encrypted,
                self.account_no_encrypted,
                self.ip_address,
            ]
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.has_credentials and self.is_enabled)

    @property
    def sandbox_simulation(self) -> bool:
        """True only when the admin explicitly enabled demonstration data."""
        return bool(self.sandbox_mode_enabled and not self.has_credentials)

    def connection_status(self) -> str:
        if self.sandbox_simulation:
            return ConnectionStatus.SANDBOX
        if not self.has_credentials:
            return ConnectionStatus.NOT_CONFIGURED
        if not self.is_enabled:
            return ConnectionStatus.CONFIGURED
        last_sync = (
            BalanceSnapshot.objects.filter(
                status=SyncStatus.SUCCESS, is_sandbox=self.sandbox_simulation
            )
            .order_by("-fetched_at")
            .first()
        )
        if self.last_test_status == ConnectionStatus.ERROR and not last_sync:
            return ConnectionStatus.ERROR
        if last_sync or self.last_test_status == ConnectionStatus.CONNECTED:
            return ConnectionStatus.CONNECTED
        return ConnectionStatus.CONFIGURED

    @property
    def sync_interval(self) -> int:
        return max(1, int(self.sync_interval_minutes or 30))


class BalanceSnapshot(TimeStampedModel):
    """Immutable history of every bank balance retrieved (or attempted)."""

    class Source(models.TextChoices):
        API = "API", "API Ecobank"
        SANDBOX = "SANDBOX", "Simulation sandbox"

    status = models.CharField(max_length=16, choices=SyncStatus.choices, default=SyncStatus.SUCCESS)
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.API)
    is_sandbox = models.BooleanField(default=False)

    available_balance = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    current_balance = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=8, blank=True, default="")
    account_no_masked = models.CharField(max_length=40, blank=True, default="")
    account_name = models.CharField(max_length=150, blank=True, default="")
    account_status = models.CharField(max_length=40, blank=True, default="")
    branch_code = models.CharField(max_length=20, blank=True, default="")

    request_id = models.CharField(max_length=64, blank=True, default="")
    response_code = models.CharField(max_length=10, blank=True, default="")
    error_message = models.CharField(max_length=500, blank=True, default="")
    fetched_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-fetched_at"]
        verbose_name = "relevé de solde bancaire"
        verbose_name_plural = "relevés de solde bancaire"

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.fetched_at:%Y-%m-%d %H:%M} {self.available_balance} {self.currency}"


class SyncLog(TimeStampedModel):
    """Log of every synchronisation attempt, including failures."""

    trigger = models.CharField(
        max_length=16, choices=SyncTrigger.choices, default=SyncTrigger.SCHEDULED
    )
    status = models.CharField(max_length=16, choices=SyncStatus.choices, default=SyncStatus.RUNNING)
    http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_code = models.CharField(max_length=10, blank=True, default="")
    message = models.CharField(max_length=500, blank=True, default="")
    duration_ms = models.PositiveIntegerField(default=0)
    is_sandbox = models.BooleanField(default=False)
    snapshot = models.ForeignKey(
        BalanceSnapshot,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sync_logs",
    )
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "journal de synchronisation"
        verbose_name_plural = "journaux de synchronisation"

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.status}"


class ApiTokenCache(models.Model):
    """Service-scoped access token cache shared by all worker processes."""

    cache_key = models.CharField(max_length=64, unique=True)
    encrypted_token = models.TextField()
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "cache de jeton API"
        verbose_name_plural = "cache de jetons API"

    @property
    def token(self) -> str:
        return decrypt_str(self.encrypted_token)

    @classmethod
    def store(cls, cache_key: str, token: str, expires_at) -> "ApiTokenCache":
        obj, _ = cls.objects.update_or_create(
            cache_key=cache_key,
            defaults={"encrypted_token": encrypt_str(token), "expires_at": expires_at},
        )
        return obj

    @classmethod
    def get_valid(cls, cache_key: str) -> str | None:
        obj = cls.objects.filter(cache_key=cache_key).first()
        if obj and obj.expires_at > timezone.now() + timedelta(seconds=30):
            try:
                return obj.token
            except Exception:
                obj.delete()
                return None
        return None

    @classmethod
    def invalidate(cls, cache_key: str) -> None:
        cls.objects.filter(cache_key=cache_key).delete()
