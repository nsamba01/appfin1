"""Optional: create a Django admin superuser for technical operations."""
from __future__ import annotations

import os

from django.core.management.base import BaseCommand

from apps.users.models import User, UserRole


class Command(BaseCommand):
    help = "Crée un superutilisateur Django à partir de DJANGO_SUPERUSER_* si défini."

    def handle(self, *args, **options):
        username = (os.getenv("DJANGO_SUPERUSER_USERNAME") or "").strip()
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD") or ""
        if not username or not password:
            self.stdout.write("DJANGO_SUPERUSER_USERNAME/PASSWORD non définis — ignoré.")
            return
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "role": UserRole.ADMIN,
                "is_staff": True,
                "is_superuser": True,
                "must_change_password": True,
            },
        )
        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Superutilisateur {username} créé."))
        else:
            self.stdout.write(f"Superutilisateur {username} déjà existant — inchangé.")
