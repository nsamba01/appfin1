"""Background worker: periodically synchronises the Ecobank balance.

The worker is a separate container. It only calls the API when a real
configuration exists and never fabricates a balance.
"""
from __future__ import annotations

import logging
import signal
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import close_old_connections

from apps.banking.models import SyncTrigger
from apps.banking.services import get_configuration, perform_sync

logger = logging.getLogger("apps.banking.worker")

RUNNING = True


def _stop(signum, frame):  # pragma: no cover - signal handling
    global RUNNING
    RUNNING = False
    logger.info("Arrêt du worker de synchronisation demandé (signal %s).", signum)


class Command(BaseCommand):
    help = "Synchronise périodiquement le solde bancaire Ecobank."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Une seule synchronisation.")
        parser.add_argument(
            "--interval", type=int, default=0, help="Intervalle en minutes (défaut : configuration)."
        )

    def handle(self, *args, **options):
        if not settings.BANK_SYNC_WORKER_ENABLED:
            self.stdout.write("Worker de synchronisation désactivé (BANK_SYNC_WORKER_ENABLED=0).")
            return

        signal.signal(signal.SIGTERM, _stop)
        signal.signal(signal.SIGINT, _stop)

        once = options["once"]
        while RUNNING:
            close_old_connections()
            try:
                config = get_configuration()
                if config.is_configured or config.sandbox_simulation:
                    outcome = perform_sync(trigger=SyncTrigger.SCHEDULED)
                    logger.info("Sync planifiée : %s — %s", outcome.log.status, outcome.message)
                else:
                    logger.info(
                        "Synchronisation ignorée : API Ecobank non configurée ou désactivée."
                    )
            except Exception:  # pragma: no cover - worker must never die
                logger.exception("Erreur dans le worker de synchronisation")

            if once:
                return

            try:
                interval = options["interval"] or get_configuration().sync_interval
            except Exception:
                interval = 30
            interval = max(1, int(interval))
            self.stdout.write(f"Prochaine synchronisation dans {interval} minute(s).")
            slept = 0
            while RUNNING and slept < interval * 60:
                time.sleep(min(5, interval * 60 - slept))
                slept += 5
