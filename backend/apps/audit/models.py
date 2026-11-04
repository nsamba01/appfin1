from __future__ import annotations

from django.conf import settings
from django.db import models


class AuditAction(models.TextChoices):
    LOGIN_SUCCESS = "LOGIN_SUCCESS", "Connexion réussie"
    LOGIN_FAILED = "LOGIN_FAILED", "Connexion échouée"
    LOGOUT = "LOGOUT", "Déconnexion"
    PASSWORD_CHANGED = "PASSWORD_CHANGED", "Mot de passe modifié"
    PASSWORD_RESET = "PASSWORD_RESET", "Mot de passe réinitialisé"
    USER_CREATED = "USER_CREATED", "Utilisateur créé"
    USER_UPDATED = "USER_UPDATED", "Utilisateur modifié"
    USER_DEACTIVATED = "USER_DEACTIVATED", "Utilisateur désactivé"
    USER_ACTIVATED = "USER_ACTIVATED", "Utilisateur activé"
    OPERATION_CREATED = "OPERATION_CREATED", "Opération créée"
    OPERATION_UPDATED = "OPERATION_UPDATED", "Opération modifiée"
    OPERATION_DELETED = "OPERATION_DELETED", "Opération supprimée"
    BANK_CONFIG_UPDATED = "BANK_CONFIG_UPDATED", "Configuration bancaire mise à jour"
    BANK_CONNECTION_TESTED = "BANK_CONNECTION_TESTED", "Test de connexion bancaire"
    BANK_SYNC = "BANK_SYNC", "Synchronisation bancaire"
    BANK_DATA_ACCESSED = "BANK_DATA_ACCESSED", "Consultation des données bancaires"
    SETTINGS_UPDATED = "SETTINGS_UPDATED", "Paramètres généraux mis à jour"
    EXPORT_GENERATED = "EXPORT_GENERATED", "Export généré"
    ACCESS_DENIED = "ACCESS_DENIED", "Accès refusé"


class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    actor_username = models.CharField(max_length=150, blank=True, default="")
    action = models.CharField(max_length=40, choices=AuditAction.choices, db_index=True)
    entity = models.CharField(max_length=60, blank=True, default="")
    entity_id = models.CharField(max_length=64, blank=True, default="")
    description = models.CharField(max_length=500, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "entrée d'audit"
        verbose_name_plural = "journal d'audit"
        indexes = [
            models.Index(fields=["action", "created_at"]),
            models.Index(fields=["entity", "entity_id"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action} {self.actor_username}"
