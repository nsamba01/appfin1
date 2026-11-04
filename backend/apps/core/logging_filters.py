"""Logging filters that guarantee no credential ever reaches the logs."""
from __future__ import annotations

import logging
import re

SENSITIVE_KEYS = (
    r"password|passwd|pwd|secret|secret_key|secretKey|client_secret|clientSecret|"
    r"access_token|refresh_token|requestToken|request_token|secureHash|secure_hash|"
    r"authorization|api[_-]?key|subscription[_-]?key|public_key|publicKey|token"
)

_PATTERNS = [
    # key=value, key: value, "key": "value"
    re.compile(
        rf"(?i)([\"']?(?:{SENSITIVE_KEYS})[\"']?)(\s*[=:]\s*)"
        r"(\"[^\"]*\"|'[^']*'|[^,;\s&}]+)"
    ),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]+"),
]


class RedactSecretsFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # pragma: no cover
            return True
        redacted = message
        for pattern in _PATTERNS:
            redacted = pattern.sub(lambda m: f"{m.group(1)}{m.group(2)}***REDACTED***", redacted)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True
