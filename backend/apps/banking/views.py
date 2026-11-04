from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditAction
from apps.audit.services import record_audit
from apps.core.permissions import IsAdministrator, IsFinanceOrAdministrator
from apps.core.utils import money

from .models import (
    BalanceSnapshot,
    ConnectionStatus,
    EcobankConfiguration,
    SyncLog,
    SyncStatus,
    SyncTrigger,
)
from .serializers import (
    BalanceSnapshotSerializer,
    EcobankConfigSerializer,
    SyncLogSerializer,
)
from .services import (
    bank_status_payload as _bank_payload,
    get_configuration,
    invalidate_token_cache,
    latest_snapshot,
    perform_sync,
    test_connection,
)


class BankingStatusView(APIView):
    """Read-only bank status for both roles. Secrets are never included."""

    permission_classes = [IsFinanceOrAdministrator]

    def get(self, request):
        config = get_configuration()
        record_audit(
            AuditAction.BANK_DATA_ACCESSED,
            entity="EcobankConfiguration",
            entity_id=config.pk,
            description="Consultation de l'état du compte bancaire Ecobank.",
        )
        return Response({"bank": _bank_payload(config)})


class BankingHistoryView(APIView):
    permission_classes = [IsFinanceOrAdministrator]

    def get(self, request):
        try:
            days = int(request.query_params.get("days", 90))
        except (TypeError, ValueError):
            return Response(
                {"detail": "Paramètre « days » invalide."}, status=status.HTTP_400_BAD_REQUEST
            )
        days = max(1, min(days, 730))
        since = timezone.now() - timezone.timedelta(days=days)
        qs = BalanceSnapshot.objects.filter(
            status=SyncStatus.SUCCESS, fetched_at__gte=since
        ).order_by("-fetched_at")[:500]
        record_audit(
            AuditAction.BANK_DATA_ACCESSED,
            entity="BalanceSnapshot",
            description=f"Consultation de l'historique des soldes bancaires ({days} jours).",
        )
        return Response(
            {
                "currency": get_configuration().currency or "—",
                "results": BalanceSnapshotSerializer(qs, many=True).data,
            }
        )


class AdminBankConfigView(APIView):
    permission_classes = [IsAdministrator]

    def get(self, request):
        config = get_configuration()
        return Response(EcobankConfigSerializer(config).data)

    def put(self, request):
        return self._update(request)

    def patch(self, request):
        return self._update(request)

    def _update(self, request):
        config = get_configuration()
        serializer = EcobankConfigSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        invalidate_token_cache()
        record_audit(
            AuditAction.BANK_CONFIG_UPDATED,
            entity="EcobankConfiguration",
            entity_id=config.pk,
            description="Mise à jour de la configuration de l'API Ecobank.",
            metadata={
                "environnement": config.environment,
                "active": config.is_enabled,
                "champs": sorted(serializer.validated_data.keys()),
            },
        )
        return Response(EcobankConfigSerializer(config).data)


class AdminBankConfigTestView(APIView):
    permission_classes = [IsAdministrator]
    throttle_scope = "bank_sync"

    def post(self, request):
        try:
            result = test_connection(user=request.user)
        except DjangoValidationError as exc:
            return Response(
                {"detail": exc.messages[0] if exc.messages else "Configuration incomplète."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(result, status=status.HTTP_200_OK)


class AdminBankSyncView(APIView):
    permission_classes = [IsAdministrator]
    throttle_scope = "bank_sync"

    def post(self, request):
        outcome = perform_sync(
            trigger=SyncTrigger.MANUAL, user=request.user, force=True
        )
        payload = SyncLogSerializer(outcome.log).data
        payload["success"] = outcome.success
        if outcome.snapshot:
            payload["snapshot"] = BalanceSnapshotSerializer(outcome.snapshot).data
        payload["bank"] = _bank_payload(get_configuration())
        return Response(
            payload,
            status=status.HTTP_200_OK if outcome.success else status.HTTP_502_BAD_GATEWAY,
        )


class AdminSyncLogsView(APIView):
    permission_classes = [IsAdministrator]

    def get(self, request):
        qs = SyncLog.objects.select_related("triggered_by").all()
        if params_status := request.query_params.get("status"):
            qs = qs.filter(status=params_status)
        if trigger := request.query_params.get("trigger"):
            qs = qs.filter(trigger=trigger)
        qs = qs[:200]
        return Response({"results": SyncLogSerializer(qs, many=True).data})


class AdminBankSecretsClearView(APIView):
    """Removes stored bank credentials (e.g. after an incident)."""

    permission_classes = [IsAdministrator]

    def post(self, request):
        config = get_configuration()
        config.secret_key = ""
        config.subscription_key = ""
        config.account_no = ""
        config.account_name = ""
        config.currency = ""
        config.is_enabled = False
        config.last_test_status = ConnectionStatus.NOT_CONFIGURED
        config.last_test_message = "Identifiants supprimés par un administrateur."
        config.save()
        invalidate_token_cache()
        record_audit(
            AuditAction.BANK_CONFIG_UPDATED,
            entity="EcobankConfiguration",
            entity_id=config.pk,
            description="Suppression des identifiants bancaires enregistrés.",
        )
        return Response({"detail": "Identifiants bancaires supprimés."})
