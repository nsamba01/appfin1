from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel


class UserRole(models.TextChoices):
    FINANCE = "FINANCE", "Financier"
    ADMIN = "ADMIN", "Administrateur"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError("Le nom d'utilisateur est obligatoire.")
        username = username.strip()
        email = extra_fields.pop("email", "") or ""
        user = self.model(username=username, email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault("role", UserRole.ADMIN)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        return self.create_user(username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    """Application user. Exactly two business roles: FINANCE and ADMIN."""

    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(blank=True, default="")
    full_name = models.CharField(max_length=150, blank=True, default="")
    role = models.CharField(max_length=16, choices=UserRole.choices, default=UserRole.FINANCE)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    must_change_password = models.BooleanField(default=False)
    password_changed_at = models.DateTimeField(null=True, blank=True)

    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    last_login_at = models.DateTimeField(null=True, blank=True)
    failed_login_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_users",
    )

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        ordering = ["username"]
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"

    def __str__(self) -> str:  # pragma: no cover - representation only
        return f"{self.username} ({self.get_role_display()})"

    # -- role helpers ------------------------------------------------------
    @property
    def is_administrator(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def is_finance(self) -> bool:
        return self.role == UserRole.FINANCE

    @property
    def display_name(self) -> str:
        return self.full_name or self.username

    # -- lockout helpers ---------------------------------------------------
    @property
    def is_locked(self) -> bool:
        return bool(self.locked_until and self.locked_until > timezone.now())

    def register_failed_login(self, max_attempts: int, lockout_minutes: int) -> None:
        from datetime import timedelta

        self.failed_login_attempts += 1
        if self.failed_login_attempts >= max_attempts:
            self.locked_until = timezone.now() + timedelta(minutes=lockout_minutes)
        self.save(update_fields=["failed_login_attempts", "locked_until", "updated_at"])

    def register_successful_login(self, ip: str | None = None) -> None:
        self.failed_login_attempts = 0
        self.locked_until = None
        self.last_login_at = timezone.now()
        if ip:
            self.last_login_ip = ip
        self.save(
            update_fields=[
                "failed_login_attempts",
                "locked_until",
                "last_login_at",
                "last_login_ip",
                "updated_at",
            ]
        )

    def set_password(self, raw_password):  # type: ignore[override]
        super().set_password(raw_password)
        self.password_changed_at = timezone.now()


class LoginAttempt(TimeStampedModel):
    """Audit trail of every authentication attempt (successes and failures)."""

    username_attempted = models.CharField(max_length=150, db_index=True)
    user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="login_attempts"
    )
    successful = models.BooleanField(default=False)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True, default="")
    reason = models.CharField(max_length=120, blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "tentative de connexion"
        verbose_name_plural = "tentatives de connexion"

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.username_attempted} @ {self.created_at:%Y-%m-%d %H:%M}"


class UserSession(models.Model):
    """Tracks issued refresh tokens so sessions can be revoked on demand."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessions")
    jti = models.CharField(max_length=64, unique=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and self.expires_at > timezone.now()
