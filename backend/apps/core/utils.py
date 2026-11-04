from __future__ import annotations

import re
from decimal import Decimal

from django.utils import timezone

ACCOUNT_RE = re.compile(r"^[0-9A-Za-z\-]{6,34}$")


def mask_account_number(account_no: str | None) -> str:
    """Mask an account number: keep the last 4 digits only."""
    if not account_no:
        return "—"
    cleaned = account_no.strip()
    if len(cleaned) <= 4:
        return "•" * len(cleaned)
    hidden = "•" * (len(cleaned) - 4)
    return f"{hidden}{cleaned[-4:]}"


def money(value) -> Decimal:
    """Quantise any numeric value to 2 decimals (banker-safe, Decimal end to end)."""
    if value is None:
        return Decimal("0.00")
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(Decimal("0.01"))


def to_decimal(value) -> Decimal:
    """Convert an API numeric value to Decimal without binary float drift.

    Ecobank may return numbers as JSON floats (e.g. 80.17). We round-trip via the
    textual representation with 4 decimals to strip float noise, then quantise.
    """
    if value is None or value == "":
        return Decimal("0.00")
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")


def client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or "0.0.0.0"


def now_local():
    return timezone.localtime(timezone.now())
