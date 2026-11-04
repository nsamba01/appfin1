"""Financial operations, balances, audit trail and exports."""
from __future__ import annotations

from decimal import Decimal

import pytest

from apps.audit.models import AuditLog
from apps.core.models import ApplicationSettings
from apps.finance.models import Operation, OperationType

from .conftest import authenticate

pytestmark = pytest.mark.django_db


class TestOperationCreation:
    def test_create_entry(self, finance_client, finance_user):
        response = finance_client.post(
            "/api/finance/operations/",
            {
                "date": "2026-11-01",
                "label": "Financement reçu",
                "amount": "5000.00",
                "operation_type": "ENTRY",
                "reference": "FIN-001",
                "observation": "Apport initial",
            },
            format="json",
        )
        assert response.status_code == 201, response.data
        assert response.data["operation_type"] == "ENTRY"
        assert response.data["signed_amount"] == "5000.00"
        assert response.data["created_by_username"] == "Emanuel"

        operation = Operation.objects.get()
        assert operation.amount == Decimal("5000.00")
        assert AuditLog.objects.filter(
            action="OPERATION_CREATED", entity_id=str(operation.pk)
        ).exists()

    def test_create_exit(self, finance_client):
        response = finance_client.post(
            "/api/finance/operations/",
            {
                "date": "2026-11-02",
                "label": "Achat de matériel",
                "amount": "1200.00",
                "operation_type": "EXIT",
            },
            format="json",
        )
        assert response.status_code == 201
        assert Operation.objects.get().signed_amount == Decimal("-1200.00")

    def test_reference_and_observation_are_optional(self, finance_client):
        response = finance_client.post(
            "/api/finance/operations/",
            {
                "date": "2026-11-02",
                "label": "Frais divers",
                "amount": "300",
                "operation_type": "EXIT",
            },
            format="json",
        )
        assert response.status_code == 201
        assert response.data["reference"] == ""
        assert response.data["observation"] == ""

    @pytest.mark.parametrize(
        "payload",
        [
            {"date": "2026-11-02", "label": "X", "amount": "10", "operation_type": "EXIT"},
            {"date": "2026-11-02", "label": "Libellé valide", "amount": "0", "operation_type": "EXIT"},
            {"date": "2026-11-02", "label": "Libellé valide", "amount": "-5", "operation_type": "EXIT"},
            {"date": "2026-11-02", "label": "Libellé valide", "amount": "10", "operation_type": "AUTRE"},
            {"label": "Libellé valide", "amount": "10", "operation_type": "EXIT"},
            {"date": "pas-une-date", "label": "Libellé valide", "amount": "10", "operation_type": "EXIT"},
        ],
    )
    def test_invalid_payloads_rejected(self, finance_client, payload):
        response = finance_client.post(
            "/api/finance/operations/", payload, format="json"
        )
        assert response.status_code == 400
        assert Operation.objects.count() == 0

    def test_amount_precision_is_preserved(self, finance_client):
        response = finance_client.post(
            "/api/finance/operations/",
            {
                "date": "2026-11-02",
                "label": "Montant décimal",
                "amount": "1234.56",
                "operation_type": "ENTRY",
            },
            format="json",
        )
        assert response.status_code == 201
        assert Operation.objects.get().amount == Decimal("1234.56")


class TestOperationRead:
    def test_list_operations(self, finance_client, operations):
        response = finance_client.get("/api/finance/operations/")
        assert response.status_code == 200
        assert response.data["count"] == 3

    def test_search_by_label(self, finance_client, operations):
        response = finance_client.get("/api/finance/operations/?search=matériel")
        assert response.data["count"] == 1
        assert response.data["results"][0]["label"] == "Achat de matériel"

    def test_filter_by_type(self, finance_client, operations):
        response = finance_client.get("/api/finance/operations/?operation_type=EXIT")
        assert response.data["count"] == 2

    def test_filter_by_period(self, finance_client, operations):
        response = finance_client.get(
            "/api/finance/operations/?date_from=2026-11-02&date_to=2026-11-03"
        )
        assert response.data["count"] == 2

    def test_detail_and_history(self, finance_client, operations):
        op = operations[0]
        assert finance_client.get(f"/api/finance/operations/{op.pk}/").status_code == 200
        history = finance_client.get(f"/api/finance/operations/{op.pk}/history/")
        assert history.status_code == 200

    def test_invalid_date_filter_does_not_crash(self, finance_client, operations):
        response = finance_client.get("/api/finance/operations/?date_from=nope")
        assert response.status_code == 200


class TestBalances:
    def test_balances_computed_server_side(self, finance_client, operations):
        response = finance_client.get("/api/finance/balances/")
        assert response.status_code == 200
        totals = response.data["totals"]
        assert totals["total_entries"] == "5000.00"
        assert totals["total_exits"] == "1500.00"
        assert totals["balance"] == "3500.00"
        assert response.data["financial_balance"] == "3500.00"

    def test_balances_respect_period(self, finance_client, operations):
        response = finance_client.get(
            "/api/finance/balances/?date_from=2026-11-03&date_to=2026-11-03"
        )
        assert response.data["totals"]["total_entries"] == "0.00"
        assert response.data["totals"]["total_exits"] == "300.00"
        assert response.data["totals"]["balance"] == "-300.00"

    def test_invalid_period_rejected(self, finance_client):
        response = finance_client.get(
            "/api/finance/balances/?date_from=2026-11-05&date_to=2026-11-01"
        )
        assert response.status_code == 400

    def test_decimal_arithmetic_has_no_float_drift(self, finance_client, db, finance_user):
        for amount in ["0.10", "0.20"]:
            Operation.objects.create(
                date="2026-11-01",
                label="Micro montant",
                amount=Decimal(amount),
                operation_type=OperationType.ENTRY,
                created_by=finance_user,
            )
        response = finance_client.get("/api/finance/balances/")
        assert response.data["totals"]["total_entries"] == "0.30"


class TestOperationUpdateDelete:
    def test_update_records_audit(self, finance_client, operations):
        op = operations[1]
        response = finance_client.patch(
            f"/api/finance/operations/{op.pk}/",
            {"amount": "1300.00", "label": "Achat de matériel (révisé)"},
            format="json",
        )
        assert response.status_code == 200
        op.refresh_from_db()
        assert op.amount == Decimal("1300.00")
        entry = AuditLog.objects.filter(
            action="OPERATION_UPDATED", entity_id=str(op.pk)
        ).first()
        assert entry is not None
        assert entry.metadata["changements"]["amount"]["avant"] == "1200.00"

    def test_delete_is_soft_and_audited(self, finance_client, operations):
        op = operations[1]
        response = finance_client.delete(f"/api/finance/operations/{op.pk}/")
        assert response.status_code == 204
        op.refresh_from_db()
        assert op.is_deleted is True
        assert op.deleted_at is not None
        assert Operation.objects.filter(pk=op.pk).exists()
        assert AuditLog.objects.filter(
            action="OPERATION_DELETED", entity_id=str(op.pk)
        ).exists()

        listing = finance_client.get("/api/finance/operations/")
        assert listing.data["count"] == 2
        assert finance_client.get(f"/api/finance/operations/{op.pk}/").status_code == 404

    def test_deleted_operations_excluded_from_balance(self, finance_client, operations):
        finance_client.delete(f"/api/finance/operations/{operations[2].pk}/")
        response = finance_client.get("/api/finance/balances/")
        assert response.data["totals"]["total_exits"] == "1200.00"
        assert response.data["totals"]["balance"] == "3800.00"

    def test_admin_sees_deleted_operations(self, admin_client, operations):
        operations[2].is_deleted = True
        operations[2].save(update_fields=["is_deleted"])
        response = admin_client.get("/api/finance/operations/?include_deleted=true")
        assert response.data["count"] == 1

    def test_edit_disabled_by_admin_setting(self, finance_client, operations):
        settings_obj = ApplicationSettings.load()
        settings_obj.allow_finance_edit_operations = False
        settings_obj.save()
        response = finance_client.patch(
            f"/api/finance/operations/{operations[0].pk}/", {"amount": "1.00"}, format="json"
        )
        assert response.status_code == 403

    def test_delete_disabled_by_admin_setting(self, finance_client, operations):
        settings_obj = ApplicationSettings.load()
        settings_obj.allow_finance_delete_operations = False
        settings_obj.save()
        response = finance_client.delete(f"/api/finance/operations/{operations[0].pk}/")
        assert response.status_code == 403

    def test_edit_window_enforced(self, finance_client, operations):
        settings_obj = ApplicationSettings.load()
        settings_obj.operation_edit_window_days = 1
        settings_obj.save()
        response = finance_client.patch(
            f"/api/finance/operations/{operations[0].pk}/", {"amount": "1.00"}, format="json"
        )
        assert response.status_code == 403

    def test_admin_bypasses_business_restrictions(self, admin_client, operations):
        settings_obj = ApplicationSettings.load()
        settings_obj.allow_finance_edit_operations = False
        settings_obj.save()
        response = admin_client.patch(
            f"/api/finance/operations/{operations[0].pk}/", {"amount": "42.00"}, format="json"
        )
        assert response.status_code == 200


class TestExports:
    def test_export_xlsx(self, finance_client, operations):
        response = finance_client.get("/api/finance/operations/export/?file_format=xlsx")
        assert response.status_code == 200
        assert response["Content-Type"].startswith(
            "application/vnd.openxmlformats-officedocument"
        )
        assert response.content[:2] == b"PK"
        assert AuditLog.objects.filter(action="EXPORT_GENERATED").exists()

    def test_export_pdf(self, finance_client, operations):
        response = finance_client.get("/api/finance/operations/export/?file_format=pdf")
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"
        payload = b"".join(response.streaming_content)
        assert payload[:4] == b"%PDF"
        assert len(payload) > 1000

    def test_export_rejects_unknown_format(self, finance_client, operations):
        response = finance_client.get("/api/finance/operations/export/?file_format=docx")
        assert response.status_code == 400

    def test_export_honours_filters(self, finance_client, operations):
        response = finance_client.get(
            "/api/finance/operations/export/?file_format=xlsx&operation_type=EXIT"
        )
        assert response.status_code == 200


class TestFinanceHistory:
    def test_history_lists_operation_events(self, finance_client, operations):
        finance_client.patch(
            f"/api/finance/operations/{operations[0].pk}/", {"amount": "5100.00"}, format="json"
        )
        response = finance_client.get("/api/finance/history/")
        assert response.status_code == 200
        assert response.data["count"] >= 1
        assert response.data["results"][0]["entity"] == "Operation"

    def test_history_search(self, finance_client, operations):
        finance_client.post(
            "/api/finance/operations/",
            {
                "date": "2026-11-04",
                "label": "Opération historique",
                "amount": "10.00",
                "operation_type": "ENTRY",
            },
            format="json",
        )
        response = finance_client.get("/api/finance/history/?search=historique")
        assert response.status_code == 200
        assert response.data["count"] >= 1
