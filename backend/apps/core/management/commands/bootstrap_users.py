"""
Secure, idempotent creation of the initial accounts.

Passwords are read from the environment ONLY — they are never written in source
code, never printed and never stored in clear text. They are hashed (Argon2id)
before insertion, and both accounts must change their password at first login.
"""
from __future__ import annotations

import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.models import ApplicationSettings
from apps.users.models import User, UserRole

ROLES = {
    "ADMIN": ("INITIAL_ADMIN_USERNAME", "INITIAL_ADMIN_PASSWORD", "ADMIN"),
    "FINANCE": ("INITIAL_FINANCE_USERNAME", "INITIAL_FINANCE_PASSWORD", "FINANCE"),
}


class Command(BaseCommand):
    help = "Crée les comptes initiaux (financier et administrateur) à partir des variables d'environnement."

    def add_arguments(self, parser):
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Échoue si une variable d'environnement requise est absente.",
        )

    def handle(self, *args, **options):
        ApplicationSettings.load()
        created = []
        skipped = []
        missing = []

        for label, (user_var, pass_var, role) in ROLES.items():
            username = (os.getenv(user_var) or "").strip()
            password = os.getenv(pass_var) or ""
            if not username:
                missing.append(user_var)
                continue
            if User.objects.filter(username__iexact=username).exists():
                skipped.append(username)
                continue
            if not password:
                missing.append(pass_var)
                continue
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username,
                    password=password,
                    role=role,
                    must_change_password=True,
                    is_active=True,
                    is_staff=(role == UserRole.ADMIN),
                    full_name="Administrateur" if role == UserRole.ADMIN else "Financier",
                )
            created.append(f"{user.username} ({role})")

        if created:
            self.stdout.write(self.style.SUCCESS("Comptes créés : " + ", ".join(created)))
        if skipped:
            self.stdout.write("Comptes déjà existants (inchangés) : " + ", ".join(skipped))
        if missing:
            message = (
                "Variables d'environnement manquantes : "
                + ", ".join(missing)
                + ". Aucun compte n'a été créé pour ces entrées."
            )
            if options["strict"] and not created:
                raise CommandError(message)
            self.stdout.write(self.style.WARNING(message))
        if not created and not skipped:
            self.stdout.write(
                self.style.WARNING(
                    "Aucun compte initial créé. Définissez INITIAL_ADMIN_USERNAME/PASSWORD "
                    "et INITIAL_FINANCE_USERNAME/PASSWORD."
                )
            )
