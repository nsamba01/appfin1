from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Max
from django.utils import timezone

from apps.banking.models import BalanceSnapshot, SyncStatus
from apps.banking.services import bank_status_payload, get_configuration
from apps.core.models import ApplicationSettings
from apps.core.utils import money
from apps.finance.exports import parse_date
from apps.finance.models import Operation
from apps.finance.services import compute_totals, monthly_series

GAP_EQUAL = "EQUAL"
GAP_FINANCIAL_HIGHER = "FINANCIAL_HIGHER"
GAP_BANK_HIGHER = "BANK_HIGHER"
GAP_UNAVAILABLE = "UNAVAILABLE"

GAP_LABELS = {
    GAP_EQUAL: "Les deux soldes sont identiques",
    GAP_FINANCIAL_HIGHER: "Le solde financier est supérieur au solde bancaire",
    GAP_BANK_HIGHER: "Le solde bancaire est supérieur au solde financier",
    GAP_UNAVAILABLE: "Comparaison indisponible (aucun solde bancaire réel)",
}


def _parse_range(params) -> tuple[date | None, date | None, str | None]:
    date_from = parse_date(params.get("date_from")) if params.get("date_from") else None
    date_to = parse_date(params.get("date_to")) if params.get("date_to") else None
    if params.get("date_from") and date_from is None:
        return None, None, "Format de date invalide pour date_from (AAAA-MM-JJ)."
    if params.get("date_to") and date_to is None:
        return None, None, "Format de date invalide pour date_to (AAAA-MM-JJ)."
    if date_from and date_to and date_from > date_to:
        return None, None, "La date de début doit précéder la date de fin."
    return date_from, date_to, None


def compute_gap(financial_balance: Decimal, bank_balance: Decimal | None) -> dict:
    """Écart = solde financier interne − solde bancaire Ecobank."""
    if bank_balance is None:
        return {
            "gap": None,
            "status": GAP_UNAVAILABLE,
            "status_label": GAP_LABELS[GAP_UNAVAILABLE],
            "absolute_gap": None,
        }
    gap = money(financial_balance - bank_balance)
    if gap == 0:
        status_value = GAP_EQUAL
    elif gap > 0:
        status_value = GAP_FINANCIAL_HIGHER
    else:
        status_value = GAP_BANK_HIGHER
    return {
        "gap": str(gap),
        "absolute_gap": str(abs(gap)),
        "status": status_value,
        "status_label": GAP_LABELS[status_value],
    }


def unreconciled_movements(last_sync_at) -> dict:
    """Internal movements that occurred after the last bank synchronisation.

    These are explicitly NOT reconciled against the bank statement; they are
    reported separately per the specification.
    """
    qs = Operation.objects.active()
    if last_sync_at:
        qs = qs.filter(created_at__gt=last_sync_at)
    aggregate = compute_totals(qs)
    return {
        "count": aggregate.operation_count,
        "total_entries": str(aggregate.total_entries),
        "total_exits": str(aggregate.total_exits),
        "net": str(aggregate.balance),
        "since": last_sync_at,
        "note": (
            "Mouvements internes enregistrés après la dernière synchronisation bancaire. "
            "Ils ne sont pas rapprochés du relevé bancaire."
        ),
    }


def bank_gap_history(limit: int = 30) -> list[dict]:
    """Compare each stored bank balance with the internal balance at that date."""
    snapshots = list(
        BalanceSnapshot.objects.filter(status=SyncStatus.SUCCESS)
        .order_by("-fetched_at")[:limit]
    )
    snapshots.reverse()
    series = []
    for snap in snapshots:
        cutoff = timezone.localtime(snap.fetched_at).date() if snap.fetched_at else None
        qs = Operation.objects.active()
        if cutoff:
            qs = qs.filter(date__lte=cutoff)
        totals = compute_totals(qs)
        bank_balance = snap.available_balance
        gap = (
            money(totals.balance - bank_balance)
            if bank_balance is not None
            else None
        )
        series.append(
            {
                "date": snap.fetched_at.isoformat() if snap.fetched_at else None,
                "label": timezone.localtime(snap.fetched_at).strftime("%d/%m %H:%M")
                if snap.fetched_at
                else "",
                "financial_balance": str(totals.balance),
                "bank_balance": str(money(bank_balance)) if bank_balance is not None else None,
                "gap": str(gap) if gap is not None else None,
                "is_sandbox": snap.is_sandbox,
            }
        )
    return series


def build_summary(params) -> tuple[dict, str | None]:
    date_from, date_to, error = _parse_range(params)
    if error:
        return {}, error

    settings_obj = ApplicationSettings.load()
    totals = compute_totals(date_from=date_from, date_to=date_to)
    bank = bank_status_payload(get_configuration())
    bank_balance = (
        Decimal(bank["available_balance"]) if bank["available_balance"] is not None else None
    )

    # Sandbox balances are never used to assert a real reconciliation.
    real_bank_balance = None if bank["is_sandbox"] else bank_balance
    gap = compute_gap(totals.balance, real_bank_balance)

    last_operation = Operation.objects.active().aggregate(last=Max("created_at"))["last"]
    unreconciled = unreconciled_movements(bank["last_sync_at"])

    alerts = []
    if bank["is_sandbox"]:
        alerts.append(
            {
                "level": "warning",
                "title": "Mode sandbox actif",
                "message": (
                    "Le solde bancaire affiché est simulé (sandbox) et ne provient pas "
                    "de l'API Ecobank. Aucun rapprochement réel n'est possible."
                ),
            }
        )
    elif not bank["is_configured"]:
        alerts.append(
            {
                "level": "info",
                "title": "API Ecobank non configurée",
                "message": (
                    "Aucun identifiant bancaire n'est enregistré. Le solde bancaire et "
                    "l'écart resteront indisponibles tant que l'administrateur n'aura pas "
                    "configuré l'API."
                ),
            }
        )
    elif bank["last_sync_status"] == "FAILED":
        alerts.append(
            {
                "level": "error",
                "title": "Dernière synchronisation échouée",
                "message": bank["last_sync_message"] or "Erreur de connexion à l'API Ecobank.",
            }
        )
    if gap["status"] not in {GAP_EQUAL, GAP_UNAVAILABLE} and not bank["is_sandbox"]:
        alerts.append(
            {
                "level": "warning",
                "title": "Écart détecté entre les deux situations",
                "message": f"{gap['status_label']} : {gap['absolute_gap']} {settings_obj.currency}.",
            }
        )

    payload = {
        "currency": settings_obj.currency,
        "company_name": settings_obj.company_name,
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "generated_at": timezone.now(),
        "financial": {
            "total_entries": str(totals.total_entries),
            "total_exits": str(totals.total_exits),
            "balance": str(totals.balance),
            "financial_balance": str(totals.balance),
            "operation_count": totals.operation_count,
            "last_operation_at": last_operation,
            "updated_at": timezone.now(),
        },
        "bank": bank,
        "comparison": {
            **gap,
            "bank_balance": bank["available_balance"],
            "financial_balance": str(totals.balance),
            "bank_is_sandbox": bank["is_sandbox"],
            "has_real_bank_data": real_bank_balance is not None,
        },
        "unreconciled": unreconciled,
        "alerts": alerts,
    }
    return payload, None


def build_charts(params) -> tuple[dict, str | None]:
    date_from, date_to, error = _parse_range(params)
    if error:
        return {}, error

    settings_obj = ApplicationSettings.load()
    monthly = monthly_series(date_from, date_to)
    bank = bank_status_payload(get_configuration())
    totals = compute_totals(date_from=date_from, date_to=date_to)

    bank_balance = (
        Decimal(bank["available_balance"]) if bank["available_balance"] is not None else None
    )
    if bank["is_sandbox"]:
        bank_balance = None

    snapshots = BalanceSnapshot.objects.filter(status=SyncStatus.SUCCESS).order_by("fetched_at")
    if date_from:
        snapshots = snapshots.filter(fetched_at__date__gte=date_from)
    if date_to:
        snapshots = snapshots.filter(fetched_at__date__lte=date_to)
    bank_history = [
        {
            "date": s.fetched_at.isoformat(),
            "label": timezone.localtime(s.fetched_at).strftime("%d/%m %H:%M"),
            "balance": str(money(s.available_balance)),
            "is_sandbox": s.is_sandbox,
        }
        for s in snapshots[:365]
        if s.available_balance is not None
    ]

    comparison = [
        {
            "indicator": "Total des entrées",
            "financial": str(totals.total_entries),
            "bank": None,
        },
        {
            "indicator": "Total des sorties",
            "financial": str(totals.total_exits),
            "bank": None,
        },
        {
            "indicator": "Solde disponible",
            "financial": str(totals.balance),
            "bank": str(bank_balance) if bank_balance is not None else None,
        },
        {"indicator": "Balance", "financial": str(totals.balance), "bank": None},
    ]

    return {
        "currency": settings_obj.currency,
        "monthly": monthly,
        "daily": [],
        "bank_history": bank_history,
        "gap_history": bank_gap_history(),
        "comparison": comparison,
        "balances_chart": [
            {
                "name": "Solde financier",
                "value": str(totals.balance),
            },
            {
                "name": "Solde bancaire",
                "value": str(bank_balance) if bank_balance is not None else None,
            },
        ],
        "bank_is_sandbox": bank["is_sandbox"],
        "bank_available": bank_balance is not None,
    }, None


def build_comparison_table(params) -> tuple[dict, str | None]:
    date_from, date_to, error = _parse_range(params)
    if error:
        return {}, error
    settings_obj = ApplicationSettings.load()
    totals = compute_totals(date_from=date_from, date_to=date_to)
    bank = bank_status_payload(get_configuration())
    bank_balance = (
        Decimal(bank["available_balance"]) if bank["available_balance"] is not None else None
    )
    if bank["is_sandbox"]:
        bank_balance = None

    rows = [
        {
            "indicator": "Total des entrées",
            "financial": str(totals.total_entries),
            "bank": None,
            "bank_note": "Non fourni par l'API",
        },
        {
            "indicator": "Total des sorties",
            "financial": str(totals.total_exits),
            "bank": None,
            "bank_note": "Non fourni par l'API",
        },
        {
            "indicator": "Solde disponible",
            "financial": str(totals.balance),
            "bank": str(bank_balance) if bank_balance is not None else None,
            "bank_note": "" if bank_balance is not None else "API Ecobank non disponible",
        },
        {
            "indicator": "Balance",
            "financial": str(totals.balance),
            "bank": None,
            "bank_note": "Non fourni par l'API",
        },
        {
            "indicator": "Date de mise à jour",
            "financial": timezone.localtime(timezone.now()).strftime("%d/%m/%Y %H:%M"),
            "bank": (
                timezone.localtime(bank["balance_updated_at"]).strftime("%d/%m/%Y %H:%M")
                if bank["balance_updated_at"]
                else None
            ),
            "bank_note": "" if bank["balance_updated_at"] else "Jamais synchronisé",
            "is_date": True,
        },
    ]
    return {
        "currency": settings_obj.currency,
        "rows": rows,
        "gap": compute_gap(totals.balance, bank_balance),
        "bank": bank,
    }, None
