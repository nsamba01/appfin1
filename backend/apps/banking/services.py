from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditAction
from apps.audit.services import record_audit
from apps.core.utils import money

from .ecobank_client import (
    BalanceResult,
    ConfigurationError,
    EcobankClient,
    EcobankError,
)
from .models import (
    ApiTokenCache,
    BalanceSnapshot,
    ConnectionStatus,
    EcobankConfiguration,
    SyncLog,
    SyncStatus,
    SyncTrigger,
)

logger = logging.getLogger("apps.banking.sync")

SANDBOX_SIMULATED_AVAILABLE = "10000.00"
SANDBOX_SIMULATED_CURRENT = "10000.00"


@dataclass
class SyncOutcome:
    log: SyncLog
    snapshot: BalanceSnapshot | None
    success: bool

    @property
    def message(self) -> str:
        return self.log.message


def get_configuration() -> EcobankConfiguration:
    return EcobankConfiguration.load()


def _set_config_result(
    config: EcobankConfiguration, status: str, message: str
) -> None:
    config.last_sync_at = timezone.now()
    config.last_sync_status = status
    config.last_sync_message = message[:500]
    config.save(update_fields=["last_sync_at", "last_sync_status", "last_sync_message", "updated_at"])


def _should_skip(config: EcobankConfiguration, trigger: str, force: bool = False) -> str | None:
    if config.sandbox_simulation:
        return None
    if not config.is_enabled:
        return "La synchronisation bancaire est désactivée dans la configuration Ecobank."
    if not config.has_credentials:
        return "Les identifiants de l'API Ecobank ne sont pas configurés."
    if force:
        # A manual sync ignores the throttling interval but never the blockers above.
        return None
    if trigger == SyncTrigger.SCHEDULED and config.auto_sync_enabled is False:
        return "La synchronisation automatique est désactivée."
    if trigger == SyncTrigger.SCHEDULED:
        latest = (
            BalanceSnapshot.objects.filter(status=SyncStatus.SUCCESS, is_sandbox=False).first()
        )
        if latest and latest.fetched_at > timezone.now() - timezone.timedelta(
            minutes=config.sync_interval
        ):
            return "Une synchronisation récente existe déjà (intervalle non écoulé)."
    return None


def perform_sync(
    *,
    trigger: str = SyncTrigger.SCHEDULED,
    user=None,
    force: bool = False,
) -> SyncOutcome:
    """Fetch the bank balance and record an immutable trace of the attempt.

    Never invents a balance: on failure no snapshot is created and the previous
    stored balance remains untouched.
    """
    started = time.monotonic()
    config = get_configuration()

    with transaction.atomic():
        config = (
            EcobankConfiguration.objects.select_for_update().filter(pk=config.pk).first()
            or config
        )
        skip_reason = _should_skip(config, trigger, force=force)
        if skip_reason:
            log = SyncLog.objects.create(
                trigger=trigger,
                status=SyncStatus.SKIPPED,
                message=skip_reason,
                duration_ms=int((time.monotonic() - started) * 1000),
                triggered_by=user if getattr(user, "pk", None) else None,
                is_sandbox=config.sandbox_simulation,
            )
            _set_config_result(config, SyncStatus.SKIPPED, skip_reason)
            return SyncOutcome(log=log, snapshot=None, success=False)

        if config.sandbox_simulation:
            snapshot = BalanceSnapshot.objects.create(
                status=SyncStatus.SUCCESS,
                source=BalanceSnapshot.Source.SANDBOX,
                is_sandbox=True,
                available_balance=money(SANDBOX_SIMULATED_AVAILABLE),
                current_balance=money(SANDBOX_SIMULATED_CURRENT),
                currency=config.currency or "USD",
                account_no_masked=config.masked_account_no or "SANDBOX-0000",
                account_name="COMPTE DE DÉMONSTRATION SANDBOX",
                account_status="SIMULATION",
                response_code="SANDBOX",
                fetched_at=timezone.now(),
            )
            message = (
                "Données de démonstration sandbox : ce solde est SIMULÉ et ne provient "
                "pas de l'API Ecobank."
            )
            log = SyncLog.objects.create(
                trigger=trigger,
                status=SyncStatus.SUCCESS,
                message=message,
                duration_ms=int((time.monotonic() - started) * 1000),
                is_sandbox=True,
                snapshot=snapshot,
                triggered_by=user if getattr(user, "pk", None) else None,
            )
            _set_config_result(config, SyncStatus.SUCCESS, message)
            record_audit(
                AuditAction.BANK_SYNC,
                actor=user,
                entity="BalanceSnapshot",
                entity_id=snapshot.pk,
                description="Synchronisation bancaire en mode sandbox (données simulées).",
                metadata={"sandbox": True, "trigger": trigger},
            )
            return SyncOutcome(log=log, snapshot=snapshot, success=True)

        client = EcobankClient(config)
        try:
            result: BalanceResult = client.get_balance()
        except ConfigurationError as exc:
            return _record_failure(config, trigger, user, started, exc.message, status_code=None)
        except EcobankError as exc:
            return _record_failure(
                config, trigger, user, started, exc.message, status_code=exc.http_status,
                response_code=getattr(exc, "response_code", ""),
            )
        except Exception:  # pragma: no cover - defensive
            logger.exception("Unexpected error during Ecobank synchronisation")
            return _record_failure(
                config,
                trigger,
                user,
                started,
                "Erreur inattendue lors de la synchronisation bancaire.",
                status_code=None,
            )

        snapshot = BalanceSnapshot.objects.create(
            status=SyncStatus.SUCCESS,
            source=BalanceSnapshot.Source.API,
            is_sandbox=False,
            available_balance=result.available_balance,
            current_balance=result.current_balance,
            currency=result.currency or config.currency,
            account_no_masked=str(result.masked_account_no),
            account_name=result.account_name,
            account_status=result.account_status,
            branch_code=result.branch_code,
            request_id=result.request_id,
            response_code=result.response_code,
            fetched_at=timezone.now(),
        )
        log = SyncLog.objects.create(
            trigger=trigger,
            status=SyncStatus.SUCCESS,
            http_status=200,
            response_code=result.response_code,
            message="Solde bancaire synchronisé avec succès depuis l'API Ecobank.",
            duration_ms=int((time.monotonic() - started) * 1000),
            snapshot=snapshot,
            triggered_by=user if getattr(user, "pk", None) else None,
        )
        config.account_no = result.account_no or config.account_no
        config.account_name = result.account_name or config.account_name
        config.currency = result.currency or config.currency
        config.last_sync_at = timezone.now()
        config.last_sync_status = SyncStatus.SUCCESS
        config.last_sync_message = "Synchronisation réussie."
        config.last_test_status = ConnectionStatus.CONNECTED
        config.save(
            update_fields=[
                "account_no_encrypted",
                "masked_account_no",
                "account_name",
                "currency",
                "last_sync_at",
                "last_sync_status",
                "last_sync_message",
                "last_test_status",
                "updated_at",
            ]
        )
        record_audit(
            AuditAction.BANK_SYNC,
            actor=user,
            entity="BalanceSnapshot",
            entity_id=snapshot.pk,
            description="Synchronisation du solde bancaire Ecobank.",
            metadata={
                "solde_disponible": str(result.available_balance),
                "devise": result.currency,
                "source": "API",
            },
        )
        logger.info(
            "Ecobank balance synchronised: %s %s", result.available_balance, result.currency
        )
        return SyncOutcome(log=log, snapshot=snapshot, success=True)


def _record_failure(
    config: EcobankConfiguration,
    trigger: str,
    user,
    started: float,
    message: str,
    *,
    status_code: int | None,
    response_code: str = "",
) -> SyncOutcome:
    log = SyncLog.objects.create(
        trigger=trigger,
        status=SyncStatus.FAILED,
        http_status=status_code,
        response_code=response_code,
        message=message[:500],
        duration_ms=int((time.monotonic() - started) * 1000),
        triggered_by=user if getattr(user, "pk", None) else None,
    )
    _set_config_result(config, SyncStatus.FAILED, message)
    if config.has_credentials and trigger != SyncTrigger.SCHEDULED:
        config.last_test_status = ConnectionStatus.ERROR
        config.save(update_fields=["last_test_status", "updated_at"])
    record_audit(
        AuditAction.BANK_SYNC,
        actor=user,
        entity="SyncLog",
        entity_id=log.pk,
        description="Échec de la synchronisation bancaire.",
        metadata={"erreur": message[:300], "trigger": trigger},
    )
    logger.warning("Ecobank synchronisation failed: %s", message)
    return SyncOutcome(log=log, snapshot=None, success=False)


def test_connection(user=None) -> dict:
    """Validate credentials against the gateway without reading a balance."""
    config = get_configuration()
    if not config.has_credentials:
        raise ValidationError(
            "Configuration incomplète : renseignez tous les identifiants avant de tester."
        )
    client = EcobankClient(config)
    started = time.monotonic()
    try:
        result = client.test_connection()
        ok = True
        message = result["message"]
        status_value = ConnectionStatus.CONNECTED
    except EcobankError as exc:
        ok = False
        message = exc.message
        status_value = ConnectionStatus.ERROR
    elapsed = int((time.monotonic() - started) * 1000)

    config.last_test_at = timezone.now()
    config.last_test_status = status_value
    config.last_test_message = message[:500]
    config.save(
        update_fields=[
            "last_test_at",
            "last_test_status",
            "last_test_message",
            "updated_at",
        ]
    )
    record_audit(
        AuditAction.BANK_CONNECTION_TESTED,
        actor=user,
        entity="EcobankConfiguration",
        entity_id=config.pk,
        description=("Test de connexion Ecobank réussi." if ok else "Test de connexion Ecobank échoué."),
        metadata={"succes": ok, "message": message[:300]},
    )
    return {
        "success": ok,
        "status": status_value,
        "message": message,
        "duration_ms": elapsed,
        "tested_at": config.last_test_at,
    }


def latest_snapshot(*, real_only: bool = False) -> BalanceSnapshot | None:
    qs = BalanceSnapshot.objects.filter(status=SyncStatus.SUCCESS)
    if real_only:
        qs = qs.filter(is_sandbox=False)
    return qs.order_by("-fetched_at").first()


def invalidate_token_cache() -> None:
    ApiTokenCache.objects.all().delete()
    logger.info("Ecobank token cache cleared after configuration change.")


def bank_status_payload(config: EcobankConfiguration | None = None) -> dict:
    """Public (secret-free) snapshot of the bank connection, for both roles."""
    from apps.core.utils import money

    config = config or get_configuration()
    snapshot = latest_snapshot()
    status_value = config.connection_status()
    available = snapshot.available_balance if snapshot else None
    return {
        "name": "Ecobank",
        "environment": config.environment,
        "environment_label": (
            "Sandbox (UAT)" if config.environment == "SANDBOX" else "Production"
        ),
        "account_masked": (
            snapshot.account_no_masked if snapshot else config.masked_account_no or "—"
        ),
        "account_name": (snapshot.account_name if snapshot else config.account_name) or "—",
        "currency": (snapshot.currency if snapshot else config.currency) or "—",
        "available_balance": str(money(available)) if available is not None else None,
        "current_balance": (
            str(money(snapshot.current_balance))
            if snapshot and snapshot.current_balance is not None
            else None
        ),
        "account_status": snapshot.account_status if snapshot else "",
        "balance_updated_at": snapshot.fetched_at if snapshot else None,
        "source": snapshot.source if snapshot else "NONE",
        "is_sandbox": bool(snapshot.is_sandbox) if snapshot else config.sandbox_simulation,
        "connection_status": status_value,
        "connection_status_label": dict(ConnectionStatus.choices).get(status_value, ""),
        "is_configured": config.has_credentials,
        "is_enabled": config.is_enabled,
        "sandbox_mode_enabled": config.sandbox_mode_enabled,
        "last_sync_at": config.last_sync_at,
        "last_sync_status": config.last_sync_status,
        "last_sync_message": config.last_sync_message,
        "last_test_at": config.last_test_at,
        "last_test_status": config.last_test_status,
        "last_test_message": config.last_test_message,
        "sync_interval_minutes": config.sync_interval,
        "auto_sync_enabled": config.auto_sync_enabled,
    }
