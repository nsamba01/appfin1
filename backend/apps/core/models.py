from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base model with creation / update timestamps."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SingletonModel(models.Model):
    """Base class for configuration tables that must contain a single row."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class ApplicationSettings(SingletonModel, TimeStampedModel):
    """General application configuration editable by administrators only."""

    company_name = models.CharField(max_length=120, default="ICHESS Finance")
    currency = models.CharField(max_length=8, default="USD")
    timezone_label = models.CharField(max_length=64, default="Africa/Kinshasa")

    # Business rules governing what a FINANCE user may do on operations.
    allow_finance_edit_operations = models.BooleanField(default=True)
    allow_finance_delete_operations = models.BooleanField(default=True)
    operation_edit_window_days = models.PositiveSmallIntegerField(
        default=0,
        help_text="0 = pas de limite. Sinon, nombre de jours pendant lesquels une opération reste modifiable.",
    )

    # Bank synchronisation frequency (minutes) used by the sync worker.
    bank_sync_interval_minutes = models.PositiveSmallIntegerField(default=30)

    class Meta:
        verbose_name = "paramètres de l'application"
        verbose_name_plural = "paramètres de l'application"

    def __str__(self) -> str:  # pragma: no cover
        return "Paramètres de l'application"
