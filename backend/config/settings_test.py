"""Test settings: isolated SQLite DB, deterministic keys, no external calls."""
from __future__ import annotations

import os

from cryptography.fernet import Fernet

os.environ.setdefault("DJANGO_DEBUG", "1")
os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-secret-key-0123456789abcdef")
os.environ.setdefault("FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode())
os.environ.setdefault("DJANGO_TESTING", "1")

from .settings import *  # noqa: E402,F401,F403

DEBUG = False

# Default to in-memory SQLite for fast unit tests. Set TEST_DATABASE_URL to run
# the very same suite against PostgreSQL (used to validate production parity).
_TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if _TEST_DATABASE_URL:
    DATABASES = {"default": dj_database_url.parse(_TEST_DATABASE_URL)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }
PASSWORD_HASHERS = ["django.contrib.auth.hashers.Argon2PasswordHasher"]
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
CORS_ALLOWED_ORIGINS = ["http://localhost:8080"]
REFRESH_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_MINUTES = 15
BANK_SYNC_WORKER_ENABLED = False
