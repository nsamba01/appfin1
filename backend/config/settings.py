"""
Django settings for the FinBank financial & banking management platform.

All environment-specific values come from environment variables (see .env.example).
Nothing sensitive is hard-coded here.
"""
from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent

# Load .env when present (local development / docker compose).
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
DEBUG = env_bool("DJANGO_DEBUG", False)

if not SECRET_KEY:
    if DEBUG or os.getenv("DJANGO_ALLOW_INSECURE_SECRET") == "1":
        SECRET_KEY = "dev-only-insecure-secret-key-change-me"
    else:
        raise RuntimeError(
            "DJANGO_SECRET_KEY is not set. Generate one with: "
            "python -c \"import secrets; print(secrets.token_urlsafe(64))\""
        )

ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver"
)
CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080"
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third party
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    # local
    "apps.core",
    "apps.users",
    "apps.audit",
    "apps.authentication",
    "apps.finance",
    "apps.banking",
    "apps.dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.SecurityHeadersMiddleware",
    "apps.core.middleware.PasswordChangeEnforcementMiddleware",
    "apps.audit.middleware.AuditRequestMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Database (PostgreSQL in Docker, SQLite only as an explicit local fallback)
# ---------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=int(os.getenv("DB_CONN_MAX_AGE", "60")),
            conn_health_checks=True,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Authentication / passwords
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "users.User"

PASSWORD_HASHERS = [
    # Argon2id is the primary hasher (OWASP recommendation for new applications).
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Sessions / CSRF / security headers
# ---------------------------------------------------------------------------
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", not DEBUG)
SESSION_COOKIE_AGE = int(os.getenv("SESSION_COOKIE_AGE", "3600"))
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

CSRF_COOKIE_HTTPONLY = False  # readable by axios to send X-CSRFToken
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", not DEBUG)
CSRF_COOKIE_AGE = 60 * 60 * 12

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", False)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", False)

# Content-Security-Policy is emitted by SecurityHeadersMiddleware.
CSP_DEFAULT_SRC = env_list("CSP_DEFAULT_SRC", "'self'")
CSP_SCRIPT_SRC = env_list("CSP_SCRIPT_SRC", "'self'")
CSP_STYLE_SRC = env_list("CSP_STYLE_SRC", "'self'", )
CSP_IMG_SRC = env_list("CSP_IMG_SRC", "'self',data:")
CSP_FONT_SRC = env_list("CSP_FONT_SRC", "'self',data:")
CSP_CONNECT_SRC = env_list("CSP_CONNECT_SRC", "'self'")

# ---------------------------------------------------------------------------
# REST framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.core.authentication.PasswordAwareJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
        "apps.core.permissions.PasswordCurrentPermission",
    ),
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 25,
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": ("apps.core.throttling.ScopedRateThrottle",),
    "DEFAULT_THROTTLE_RATES": {
        "login": os.getenv("THROTTLE_LOGIN", "20/min"),
        "sensitive": os.getenv("THROTTLE_SENSITIVE", "60/min"),
        "bank_sync": os.getenv("THROTTLE_BANK_SYNC", "6/min"),
        "export": os.getenv("THROTTLE_EXPORT", "10/min"),
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=int(os.getenv("JWT_ACCESS_MINUTES", "15"))
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        minutes=int(os.getenv("JWT_REFRESH_MINUTES", "480"))
    ),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "TOKEN_OBTAIN_SERIALIZER": "apps.authentication.serializers.CustomTokenObtainPairSerializer",
}

# The refresh token is delivered as an HttpOnly cookie; the access token stays in
# browser memory only (never localStorage) — see docs/SECURITY.md.
REFRESH_COOKIE_NAME = os.getenv("REFRESH_COOKIE_NAME", "finbank_refresh")
REFRESH_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", not DEBUG)
REFRESH_COOKIE_SAMESITE = os.getenv("REFRESH_COOKIE_SAMESITE", "Lax")
REFRESH_COOKIE_PATH = "/api/auth/"

# ---------------------------------------------------------------------------
# CORS / CSRF for the SPA
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080"
)
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]
CORS_ALLOW_METHODS = ["DELETE", "GET", "OPTIONS", "PATCH", "POST", "PUT"]

# ---------------------------------------------------------------------------
# Localisation / currency
# ---------------------------------------------------------------------------
LANGUAGE_CODE = os.getenv("LANGUAGE_CODE", "fr-fr")
TIME_ZONE = os.getenv("TIME_ZONE", "Africa/Kinshasa")
USE_I18N = True
USE_TZ = True

APP_CURRENCY = os.getenv("APP_CURRENCY", "USD")
APP_COMPANY_NAME = os.getenv("APP_COMPANY_NAME", "ICHESS Finance")

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# ---------------------------------------------------------------------------
# Logging — never log secrets or passwords.
# ---------------------------------------------------------------------------
LOG_LEVEL = os.getenv("DJANGO_LOG_LEVEL", "INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
        "simple": {"format": "{levelname} {name} {message}", "style": "{"},
    },
    "filters": {
        "redact": {"()": "apps.core.logging_filters.RedactSecretsFilter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
            "filters": ["redact"],
        },
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "apps": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "apps.banking": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}

# ---------------------------------------------------------------------------
# Encryption key used for bank API secrets at rest.
# Must be a Fernet key: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# ---------------------------------------------------------------------------
FIELD_ENCRYPTION_KEY = os.getenv("FIELD_ENCRYPTION_KEY", "")

# ---------------------------------------------------------------------------
# Security behaviour
# ---------------------------------------------------------------------------
MAX_LOGIN_ATTEMPTS = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
LOGIN_LOCKOUT_MINUTES = int(os.getenv("LOGIN_LOCKOUT_MINUTES", "15"))
LOGIN_ATTEMPT_WINDOW_MINUTES = int(os.getenv("LOGIN_ATTEMPT_WINDOW_MINUTES", "15"))

# Bank synchronisation defaults (overridable in the admin UI).
ECOBANK_DEFAULT_BASE_URL = os.getenv(
    "ECOBANK_BASE_URL", "https://apimuat-gateway.ecobank.com"
)
ECOBANK_DEFAULT_AUTH_PATH = os.getenv(
    "ECOBANK_AUTH_PATH", "/corp-auth/api/v2/integration/auth/app/token"
)
ECOBANK_DEFAULT_BALANCE_PATH = os.getenv(
    "ECOBANK_BALANCE_PATH",
    "/corp-account-inquiry/api/v2/integration/account/inquiry/balance",
)
ECOBANK_HTTP_TIMEOUT = int(os.getenv("ECOBANK_HTTP_TIMEOUT", "30"))
BANK_SYNC_INTERVAL_MINUTES = int(os.getenv("BANK_SYNC_INTERVAL_MINUTES", "30"))

# Hard guard: the sync worker refuses to start if the API is not configured.
BANK_SYNC_WORKER_ENABLED = env_bool("BANK_SYNC_WORKER_ENABLED", True)

TESTING = os.getenv("DJANGO_TESTING") == "1"
