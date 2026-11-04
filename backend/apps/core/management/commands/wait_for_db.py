import time

from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.utils import OperationalError


class Command(BaseCommand):
    help = "Attend que la base de données PostgreSQL soit disponible."

    def add_arguments(self, parser):
        parser.add_argument("--timeout", type=int, default=60)
        parser.add_argument("--interval", type=float, default=1.5)

    def handle(self, *args, **options):
        timeout = options["timeout"]
        interval = options["interval"]
        deadline = time.monotonic() + timeout
        attempt = 0
        while True:
            attempt += 1
            try:
                connections["default"].ensure_connection()
                self.stdout.write(self.style.SUCCESS("Base de données disponible."))
                return
            except OperationalError as exc:
                if time.monotonic() >= deadline:
                    raise CommandError(
                        f"Base de données indisponible après {timeout}s : {exc}"
                    ) from exc
                self.stdout.write(
                    f"Attente de la base de données (tentative {attempt})..."
                )
                time.sleep(interval)
