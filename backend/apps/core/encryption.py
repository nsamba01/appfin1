"""
Symmetric encryption helpers for sensitive data at rest (bank API secrets).

A dedicated key (FIELD_ENCRYPTION_KEY) is used so that rotating the Django
SECRET_KEY does not make stored bank credentials unreadable. When the dedicated
key is absent (development only), a key is derived from SECRET_KEY with HKDF and
a warning is logged.
"""
from __future__ import annotations

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings

logger = logging.getLogger("apps.core.encryption")


class EncryptionError(RuntimeError):
    pass


def _fernet() -> Fernet:
    key = getattr(settings, "FIELD_ENCRYPTION_KEY", "") or ""
    if key:
        try:
            return Fernet(key.encode() if isinstance(key, str) else key)
        except Exception as exc:  # pragma: no cover - configuration error
            raise EncryptionError(
                "FIELD_ENCRYPTION_KEY is not a valid Fernet key. Generate one with: "
                "python -c \"from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())\""
            ) from exc

    logger.warning(
        "FIELD_ENCRYPTION_KEY is not set — deriving an encryption key from "
        "SECRET_KEY. Set a dedicated key before going to production."
    )
    derived = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=b"finbank-field-encryption", info=b"v1"
    ).derive(settings.SECRET_KEY.encode())
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_str(value: str | None) -> str:
    if value in (None, ""):
        return ""
    return _fernet().encrypt(value.encode()).decode()


def decrypt_str(value: str | None) -> str:
    if value in (None, ""):
        return ""
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise EncryptionError(
            "Unable to decrypt a stored secret. FIELD_ENCRYPTION_KEY may have changed."
        ) from exc


def secret_fingerprint(value: str) -> str:
    """Stable non-reversible fingerprint, used only to show that a secret exists."""
    if not value:
        return ""
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def mask_secret(value: str | None, visible: int = 4) -> str:
    """Mask a secret for display: keeps only a short, non-sensitive suffix."""
    if not value:
        return "—"
    if len(value) <= visible:
        return "•" * len(value)
    return "•" * max(4, len(value) - visible) + value[-visible:]
