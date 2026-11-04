from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db import transaction
from django.http import FileResponse, HttpResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditAction, AuditLog
from apps.audit.serializers import AuditLogSerializer
from apps.audit.services import record_audit
from apps.core.models import ApplicationSettings
from apps.core.permissions import IsFinanceOrAdministrator

from .exports import build_operations_pdf, build_operations_workbook, parse_date
from .models import Operation
from .serializers import OperationSerializer, OperationWriteSerializer
from .services import compute_totals, daily_series, monthly_series


def _parse_param_date(value, name):
    if not value:
        return None
    parsed = parse_date(value)
    if parsed is None:
        raise ValueError(f"Format de date invalide pour {name} (attendu AAAA-MM-JJ).")
    return parsed


class OperationViewSet(viewsets.ModelViewSet):
    """Internal financial operations — FINANCE and ADMIN."""

    permission_classes = [IsFinanceOrAdministrator]
    queryset = Operation.objects.select_related("created_by", "updated_by").all()

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return OperationWriteSerializer
        return OperationSerializer

    # -- queryset filters --------------------------------------------------
    def get_queryset(self):
        qs = Operation.objects.select_related("created_by", "updated_by")
        include_deleted = self.request.query_params.get("include_deleted") == "true"
        if include_deleted and self.request.user.is_administrator:
            qs = qs.filter(is_deleted=True)
        else:
            qs = qs.filter(is_deleted=False)

        params = self.request.query_params
        if date_from := params.get("date_from"):
            if parse_date(date_from):
                qs = qs.filter(date__gte=parse_date(date_from))
        if date_to := params.get("date_to"):
            if parse_date(date_to):
                qs = qs.filter(date__lte=parse_date(date_to))
        if op_type := params.get("operation_type"):
            qs = qs.filter(operation_type=op_type)
        if search := params.get("search"):
            from django.db.models import Q

            qs = qs.filter(
                Q(label__icontains=search)
                | Q(reference__icontains=search)
                | Q(observation__icontains=search)
            )
        ordering = params.get("ordering", "-date")
        allowed = {
            "date",
            "-date",
            "amount",
            "-amount",
            "label",
            "-label",
            "created_at",
            "-created_at",
        }
        qs = qs.order_by(ordering if ordering in allowed else "-date", "-created_at")
        return qs

    # -- write operations --------------------------------------------------
    def _check_edit_permission(self, operation: Operation):
        user = self.request.user
        if user.is_administrator:
            return
        app_settings = ApplicationSettings.load()
        if not app_settings.allow_finance_edit_operations:
            raise PermissionDenied(
                "La modification des opérations est désactivée par l'administrateur."
            )
        window = app_settings.operation_edit_window_days
        if window:
            limit = operation.date + timedelta(days=window)
            if date.today() > limit:
                raise PermissionDenied(
                    f"Cette opération n'est plus modifiable (fenêtre de {window} jours)."
                )

    def create(self, request, *args, **kwargs):
        serializer = OperationWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        operation = serializer.save(created_by=request.user)
        record_audit(
            AuditAction.OPERATION_CREATED,
            entity="Operation",
            entity_id=operation.pk,
            description=f"Création de l'opération « {operation.label} »",
            metadata={
                "montant": str(operation.amount),
                "type": operation.operation_type,
                "date": operation.date.isoformat(),
                "reference": operation.reference,
            },
        )
        return Response(OperationSerializer(operation).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        self._check_edit_permission(instance)
        serializer = OperationWriteSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        before = {
            "label": instance.label,
            "amount": str(instance.amount),
            "operation_type": instance.operation_type,
            "date": instance.date.isoformat(),
            "reference": instance.reference,
            "observation": instance.observation,
        }
        operation = serializer.save(updated_by=request.user)
        after = {
            "label": operation.label,
            "amount": str(operation.amount),
            "operation_type": operation.operation_type,
            "date": operation.date.isoformat(),
            "reference": operation.reference,
            "observation": operation.observation,
        }
        changes = {
            key: {"avant": before[key], "après": after[key]}
            for key in before
            if before[key] != after[key]
        }
        record_audit(
            AuditAction.OPERATION_UPDATED,
            entity="Operation",
            entity_id=operation.pk,
            description=f"Modification de l'opération « {operation.label} »",
            metadata={"changements": changes},
        )
        return Response(OperationSerializer(operation).data)

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        user = request.user
        app_settings = ApplicationSettings.load()
        if not user.is_administrator and not app_settings.allow_finance_delete_operations:
            raise PermissionDenied(
                "La suppression des opérations est désactivée par l'administrateur."
            )
        self._check_edit_permission(instance)
        with transaction.atomic():
            instance.is_deleted = True
            instance.deleted_at = timezone.now()
            instance.deleted_by = user
            instance.save(
                update_fields=["is_deleted", "deleted_at", "deleted_by", "updated_at"]
            )
            record_audit(
                AuditAction.OPERATION_DELETED,
                entity="Operation",
                entity_id=instance.pk,
                description=f"Suppression (archivage) de l'opération « {instance.label} »",
                metadata={
                    "montant": str(instance.amount),
                    "type": instance.operation_type,
                    "date": instance.date.isoformat(),
                },
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    # -- read helpers ------------------------------------------------------
    @action(detail=True, methods=["get"], url_path="history")
    def history(self, request, pk=None):
        operation = self.get_object()
        entries = AuditLog.objects.filter(entity="Operation", entity_id=str(operation.pk))
        return Response(AuditLogSerializer(entries, many=True).data)

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        self.throttle_scope = "export"
        file_format = (request.query_params.get("file_format") or "xlsx").lower()
        if file_format not in {"xlsx", "pdf"}:
            return Response(
                {"detail": "Format d'export non supporté (xlsx ou pdf)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            qs = self.get_queryset()
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        qs = qs.filter(is_deleted=False).order_by("date", "created_at")[:5000]
        operations = list(qs)
        totals = compute_totals(Operation.objects.all().filter(pk__in=[o.pk for o in operations]))
        app_settings = ApplicationSettings.load()
        currency = app_settings.currency
        company = app_settings.company_name

        record_audit(
            AuditAction.EXPORT_GENERATED,
            entity="Operation",
            description=f"Export {file_format.upper()} de {len(operations)} opération(s).",
            metadata={"format": file_format, "count": len(operations)},
        )

        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        if file_format == "xlsx":
            wb = build_operations_workbook(operations, totals, currency, company)
            response = HttpResponse(
                content_type=(
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            )
            wb.save(response)
            response["Content-Disposition"] = (
                f'attachment; filename="operations_{stamp}.xlsx"'
            )
            return response

        buffer = build_operations_pdf(operations, totals, currency, company)
        return FileResponse(
            buffer,
            as_attachment=True,
            filename=f"operations_{stamp}.pdf",
            content_type="application/pdf",
        )


class BalanceView(APIView):
    """Server-computed balances and series for the balances page."""

    permission_classes = [IsFinanceOrAdministrator]

    def get(self, request):
        try:
            date_from = _parse_param_date(request.query_params.get("date_from"), "date_from")
            date_to = _parse_param_date(request.query_params.get("date_to"), "date_to")
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if date_from and date_to and date_from > date_to:
            return Response(
                {"detail": "La date de début doit précéder la date de fin."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        totals = compute_totals(date_from=date_from, date_to=date_to)
        settings_obj = ApplicationSettings.load()
        return Response(
            {
                "currency": settings_obj.currency,
                "date_from": date_from.isoformat() if date_from else None,
                "date_to": date_to.isoformat() if date_to else None,
                "totals": totals.as_dict(),
                # Balance financière == total entrées - total sorties (spec §3.B).
                "financial_balance": str(totals.balance),
                "monthly_series": monthly_series(date_from, date_to),
                "daily_series": daily_series(date_from, date_to),
            }
        )


class FinanceHistoryView(APIView):
    """Operation audit trail readable by financiers and administrators."""

    permission_classes = [IsFinanceOrAdministrator]

    def get(self, request):
        qs = AuditLog.objects.filter(entity="Operation").select_related("actor")
        if search := request.query_params.get("search"):
            qs = qs.filter(description__icontains=search)
        if action := request.query_params.get("action"):
            qs = qs.filter(action=action)
        if date_from := request.query_params.get("date_from"):
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to := request.query_params.get("date_to"):
            qs = qs.filter(created_at__date__lte=date_to)

        from apps.core.pagination import StandardPagination

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(AuditLogSerializer(page, many=True).data)
