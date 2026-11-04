from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Q, Sum

from apps.core.utils import money

from .models import Operation, OperationType


@dataclass(frozen=True)
class FinancialTotals:
    total_entries: Decimal
    total_exits: Decimal
    balance: Decimal
    operation_count: int

    def as_dict(self) -> dict:
        return {
            "total_entries": str(money(self.total_entries)),
            "total_exits": str(money(self.total_exits)),
            "balance": str(money(self.balance)),
            "operation_count": self.operation_count,
        }


def compute_totals(queryset=None, date_from=None, date_to=None) -> FinancialTotals:
    """Server-side totals. Money never relies on browser arithmetic."""
    qs = (queryset if queryset is not None else Operation.objects.all()).filter(
        is_deleted=False
    )
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)

    aggregated = qs.aggregate(
        entries=Sum("amount", filter=Q(operation_type=OperationType.ENTRY)),
        exits=Sum("amount", filter=Q(operation_type=OperationType.EXIT)),
    )
    entries = aggregated["entries"] or Decimal("0.00")
    exits = aggregated["exits"] or Decimal("0.00")
    return FinancialTotals(
        total_entries=money(entries),
        total_exits=money(exits),
        balance=money(entries - exits),
        operation_count=qs.count(),
    )


def monthly_series(date_from=None, date_to=None) -> list[dict]:
    """Monthly entries / exits / running balance, computed with Decimal only."""
    qs = Operation.objects.active()
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    buckets: dict[str, dict[str, Decimal]] = {}
    for op in qs.order_by("date").only("date", "amount", "operation_type"):
        key = f"{op.date.year:04d}-{op.date.month:02d}"
        bucket = buckets.setdefault(
            key, {"entries": Decimal("0.00"), "exits": Decimal("0.00")}
        )
        if op.operation_type == OperationType.ENTRY:
            bucket["entries"] += op.amount
        else:
            bucket["exits"] += op.amount

    series = []
    running = Decimal("0.00")
    for key in sorted(buckets):
        entries = money(buckets[key]["entries"])
        exits = money(buckets[key]["exits"])
        running = money(running + entries - exits)
        series.append(
            {
                "period": key,
                "entries": str(entries),
                "exits": str(exits),
                "balance": str(running),
            }
        )
    return series


def daily_series(date_from=None, date_to=None) -> list[dict]:
    """Daily net flow, useful for the evolution chart on short ranges."""
    qs = Operation.objects.active()
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    buckets: dict[str, dict[str, Decimal]] = {}
    for op in qs.order_by("date").only("date", "amount", "operation_type"):
        key = op.date.isoformat()
        bucket = buckets.setdefault(
            key, {"entries": Decimal("0.00"), "exits": Decimal("0.00")}
        )
        if op.operation_type == OperationType.ENTRY:
            bucket["entries"] += op.amount
        else:
            bucket["exits"] += op.amount
    result = []
    for key in sorted(buckets):
        result.append(
            {
                "period": key,
                "entries": str(money(buckets[key]["entries"])),
                "exits": str(money(buckets[key]["exits"])),
                "net": str(money(buckets[key]["entries"] - buckets[key]["exits"])),
            }
        )
    return result
