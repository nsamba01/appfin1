from __future__ import annotations

import logging

from apps.core.utils import client_ip

from .middleware import get_current_request
from .models import AuditLog

logger = logging.getLogger("apps.audit")


def record_audit(
    action: str,
    *,
    actor=None,
    entity: str = "",
    entity_id: str | int = "",
    description: str = "",
    metadata: dict | None = None,
    request=None,
) -> AuditLog:
    """Persist an audit entry. Never pass passwords or secrets in metadata."""
    req = request or get_current_request()
    ip = None
    user_agent = ""
    if req is not None:
        try:
            ip = client_ip(req)
        except Exception:  # pragma: no cover
            ip = None
        user_agent = (req.META.get("HTTP_USER_AGENT") or "")[:255]

    if actor is None and req is not None:
        candidate = getattr(req, "user", None)
        if candidate is not None and candidate.is_authenticated:
            actor = candidate

    entry = AuditLog.objects.create(
        actor=actor if getattr(actor, "pk", None) else None,
        actor_username=getattr(actor, "username", "") or "",
        action=action,
        entity=entity,
        entity_id=str(entity_id or ""),
        description=description[:500],
        metadata=metadata or {},
        ip_address=ip,
        user_agent=user_agent,
    )
    logger.info("audit %s by=%s entity=%s/%s", action, entry.actor_username, entity, entity_id)
    return entry
