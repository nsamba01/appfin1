from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import TimeStampedModel


class OperationType(models.TextChoices):
    ENTRY = "ENTRY", "Entrée"
    EXIT = "EXIT", "Sortie"


class OperationQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_deleted=False)

    def entries(self):
        return self.active().filter(operation_type=OperationType.ENTRY)

    def exits(self):
        return self.active().filter(operation_type=OperationType.EXIT)


class Operation(TimeStampedModel):
    """An internal financial operation (money in or money out).

    Records are never hard-deleted: a deletion marks the row and keeps it in the
    audit trail so no validated operation can disappear silently.
    """

    date = models.DateField(db_index=True)
    label = models.CharField(max_length=180)
    amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    operation_type = models.CharField(
        max_length=8, choices=OperationType.choices, db_index=True
    )
    reference = models.CharField(max_length=64, blank=True, default="")
    observation = models.TextField(blank=True, default="")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="operations_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="operations_updated",
    )

    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="operations_deleted",
    )

    objects = OperationQuerySet.as_manager()

    class Meta:
        ordering = ["-date", "-created_at"]
        verbose_name = "opération financière"
        verbose_name_plural = "opérations financières"
        indexes = [
            models.Index(fields=["date", "operation_type"]),
            models.Index(fields=["is_deleted", "date"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="operation_amount_positive"
            )
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.date} {self.label} ({self.operation_type})"

    @property
    def signed_amount(self) -> Decimal:
        amount = self.amount or Decimal("0.00")
        return amount if self.operation_type == OperationType.ENTRY else -amount
