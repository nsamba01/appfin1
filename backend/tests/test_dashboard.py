"""Dashboard aggregation, comparison table and gap computation."""
from __future__ import annotations

from decimal import Decimal

import pytest
from django.utils import timezone

from apps.banking.models import BalanceSnapshot, SyncStatus
from apps.dashboard.services import GAP_BANK_HIGHER, GAP_EQUAL, GAP_FINANCIAL_HIGHER, compute_gap

pytestmark = pytest.mark.django_db


def add_bank_balance(amount: str, *, sandbox: bool = False) -> BalanceSnapshot:
    return BalanceSnapshot.objects.create(
        status=SyncStatus.SUCCESS,
        source=BalanceSnapshot.Source.SANDBOX if sandbox else BalanceSnapshot.Source.API,
        is_sandbox=sandbox,
        available_balance=Decimal(amount),
        current_balance=Decimal(amount),
        currency="USD",
        account_no_masked="••••••6858",
        account_name="ICHESS FINANCE",
        account_status="ACTIVE",
        fetched_at=timezone.now(),
    )


class TestGapComputation:
    def test_equal_balances(self):
        gap = compute_gap(Decimal("100.00"), Decimal("100.00"))
        assert gap["status"] == GAP_EQUAL
        assert gap["gap"] == "0.00"

    def test_financial_higher(self):
        gap = compute_gap(Decimal("150.00"), Decimal("100.00"))
        assert gap["status"] == GAP_FINANCIAL_HIGHER
        assert gap["gap"] == "50.00"

    def test_bank_higher(self):
        gap = compute_gap(Decimal("50.00"), Decimal("100.00"))
        assert gap["status"] == GAP_BANK_HIGHER
        assert gap["gap"] == "-50.00"
        assert gap["absolute_gap"] == "50.00"

    def test_unavailable_without_bank_balance(self):
        gap = compute_gap(Decimal("50.00"), None)
        assert gap["status"] == "UNAVAILABLE"
        assert gap["gap"] is None


class TestSummary:
    def test_summary_without_bank_data(self, finance_client, operations):
        response = finance_client.get("/api/dashboard/summary/")
        assert response.status_code == 200
        data = response.data
        assert data["financial"]["total_entries"] == "5000.00"
        assert data["financial"]["total_exits"] == "1500.00"
        assert data["financial"]["balance"] == "3500.00"
        assert data["bank"]["available_balance"] is None
        assert data["comparison"]["status"] == "UNAVAILABLE"
        assert any(alert["level"] == "info" for alert in data["alerts"])

    def test_summary_gap_with_real_bank_balance(self, finance_client, operations):
        add_bank_balance("3000.00")
        response = finance_client.get("/api/dashboard/summary/")
        assert response.data["comparison"]["gap"] == "500.00"
        assert response.data["comparison"]["status"] == GAP_FINANCIAL_HIGHER
        assert response.data["comparison"]["has_real_bank_data"] is True

    def test_summary_ignores_sandbox_balance_for_gap(self, finance_client, operations):
        add_bank_balance("3000.00", sandbox=True)
        response = finance_client.get("/api/dashboard/summary/")
        assert response.data["comparison"]["status"] == "UNAVAILABLE"
        assert response.data["comparison"]["bank_is_sandbox"] is True

    def test_unreconciled_movements_reported_separately(self, finance_client, operations):
        response = finance_client.get("/api/dashboard/summary/")
        unreconciled = response.data["unreconciled"]
        assert unreconciled["count"] == 3
        assert "rapproch" in unreconciled["note"]

    def test_summary_period_filter(self, finance_client, operations):
        response = finance_client.get(
            "/api/dashboard/summary/?date_from=2026-11-02&date_to=2026-11-02"
        )
        assert response.data["financial"]["total_entries"] == "0.00"
        assert response.data["financial"]["total_exits"] == "1200.00"

    def test_invalid_period_returns_400(self, finance_client):
        response = finance_client.get("/api/dashboard/summary/?date_from=bad-date")
        assert response.status_code == 400


class TestComparisonTable:
    def test_rows_present(self, finance_client, operations):
        add_bank_balance("3000.00")
        response = finance_client.get("/api/dashboard/comparison/")
        assert response.status_code == 200
        indicators = [row["indicator"] for row in response.data["rows"]]
        assert indicators == [
            "Total des entrées",
            "Total des sorties",
            "Solde disponible",
            "Balance",
            "Date de mise à jour",
        ]
        solde = response.data["rows"][2]
        assert solde["financial"] == "3500.00"
        assert solde["bank"] == "3000.00"
        date_row = response.data["rows"][4]
        assert date_row["bank"] is not None


class TestCharts:
    def test_charts_payload(self, finance_client, operations):
        add_bank_balance("3000.00")
        response = finance_client.get("/api/dashboard/charts/")
        assert response.status_code == 200
        data = response.data
        assert len(data["monthly"]) >= 1
        assert data["monthly"][0]["period"].startswith("2026-11")
        assert data["monthly"][0]["entries"] == "5000.00"
        assert data["monthly"][0]["exits"] == "1500.00"
        assert data["monthly"][0]["balance"] == "3500.00"
        assert len(data["bank_history"]) == 1
        assert len(data["gap_history"]) == 1
        assert data["gap_history"][0]["gap"] == "500.00"
        assert data["bank_available"] is True

    def test_charts_never_use_sandbox_as_real_balance(self, finance_client, operations):
        add_bank_balance("3000.00", sandbox=True)
        response = finance_client.get("/api/dashboard/charts/")
        assert response.data["bank_available"] is False
        assert response.data["bank_is_sandbox"] is True
