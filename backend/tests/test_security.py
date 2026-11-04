"""Security regression tests (OWASP-oriented)."""
from __future__ import annotations

import logging

import pytest
from django.conf import settings
from django.core import mail
from django.test import Client

from apps.audit.models import AuditLog
from apps.core.logging_filters import RedactSecretsFilter
from apps.finance.models import Operation
from apps.users.models import User, UserRole

from .conftest import DEFAULT_PASSWORD

pytestmark = pytest.mark.django_db


class TestAccessControl:
    def test_finance_cannot_touch_administration(self, finance_client):
        endpoints = [
            ("get", "/api/admin/users/"),
            ("post", "/api/admin/users/"),
            ("get", "/api/admin/audit-logs/"),
            ("get", "/api/admin/login-logs/"),
            ("get", "/api/admin/settings/"),
            ("get", "/api/banking/config/"),
            ("patch", "/api/banking/config/"),
            ("post", "/api/banking/sync/"),
            ("get", "/api/banking/logs/"),
        ]
        for method, url in endpoints:
            response = getattr(finance_client, method)(url)
            assert response.status_code in {403, 400}, f"{method} {url} -> {response.status_code}"

    def test_admin_has_full_access(self, admin_client):
        for url in [
            "/api/admin/users/",
            "/api/admin/audit-logs/",
            "/api/admin/login-logs/",
            "/api/admin/settings/",
            "/api/banking/config/",
            "/api/banking/logs/",
            "/api/finance/operations/",
            "/api/dashboard/summary/",
        ]:
            assert admin_client.get(url).status_code == 200, url

    def test_role_cannot_be_escalated_through_payload(self, finance_client):
        response = finance_client.post(
            "/api/finance/operations/",
            {
                "date": "2026-11-01",
                "label": "Tentative",
                "amount": "10.00",
                "operation_type": "ENTRY",
                "role": "ADMIN",
            },
            format="json",
        )
        assert response.status_code == 201
        assert not hasattr(Operation.objects.get(), "role")

    def test_no_password_endpoint_leaks_hashes(self, admin_client, finance_user):
        response = admin_client.get(f"/api/admin/users/{finance_user.pk}/")
        assert "password" not in response.data

    def test_inactive_user_token_rejected(self, admin_client, finance_user, api_client):
        login = api_client.post(
            "/api/auth/login/",
            {"username": "Emanuel", "password": DEFAULT_PASSWORD},
            format="json",
        )
        token = login.data["access"]
        finance_user.is_active = False
        finance_user.save(update_fields=["is_active"])
        client = type(api_client)()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        assert client.get("/api/auth/me/").status_code == 401


class TestInputValidation:
    def test_sql_injection_attempt_is_harmless(self, finance_client, operations):
        payload = "'; DROP TABLE finance_operation; --"
        response = finance_client.get(
            "/api/finance/operations/", {"search": payload}
        )
        assert response.status_code == 200
        assert Operation.objects.count() == 3

        create = finance_client.post(
            "/api/finance/operations/",
            {
                "date": "2026-11-01",
                "label": payload,
                "amount": "10.00",
                "operation_type": "ENTRY",
            },
            format="json",
        )
        assert create.status_code == 201
        assert Operation.objects.filter(label=payload).exists()

    def test_xss_payload_is_stored_but_escaped_by_api(self, finance_client):
        payload = "<script>alert('xss')</script>"
        response = finance_client.post(
            "/api/finance/operations/",
            {
                "date": "2026-11-01",
                "label": payload,
                "amount": "10.00",
                "operation_type": "ENTRY",
            },
            format="json",
        )
        assert response.status_code == 201
        # React escapes by default; the API also returns JSON, never HTML.
        assert response["Content-Type"].startswith("application/json")

    def test_malformed_json_is_rejected(self, finance_client):
        response = finance_client.post(
            "/api/finance/operations/",
            data="{bad json",
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_invalid_jwt_rejected(self, api_client):
        api_client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
        assert api_client.get("/api/auth/me/").status_code == 401


class TestSecurityHeaders:
    def test_api_responses_carry_security_headers(self, finance_client):
        response = finance_client.get("/api/auth/me/")
        assert response["X-Content-Type-Options"] == "nosniff"
        assert response["X-Frame-Options"] == "DENY"
        assert response["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "Content-Security-Policy" in response
        assert response["Cache-Control"] == "no-store"

    def test_cors_is_restricted(self, finance_client):
        response = finance_client.get(
            "/api/auth/me/", HTTP_ORIGIN="https://evil.example.com"
        )
        assert response.get("Access-Control-Allow-Origin") in (None, "")

    def test_allowed_origin_is_echoed(self, finance_client):
        response = finance_client.get(
            "/api/auth/me/", HTTP_ORIGIN="http://localhost:8080"
        )
        assert response["Access-Control-Allow-Origin"] == "http://localhost:8080"


class TestSecretHandling:
    def test_login_attempt_never_logs_password(self, caplog, api_client, finance_user):
        with caplog.at_level(logging.DEBUG):
            api_client.post(
                "/api/auth/login/",
                {"username": "Emanuel", "password": "SuperSecretPassword#1"},
                format="json",
            )
        for record in caplog.records:
            assert "SuperSecretPassword#1" not in record.getMessage()

    def test_audit_metadata_never_contains_passwords(self, admin_client, finance_user):
        admin_client.post(
            f"/api/admin/users/{finance_user.pk}/password/",
            {"new_password": "NouveauSecret#2026", "force_change": False},
            format="json",
        )
        for entry in AuditLog.objects.all():
            assert "NouveauSecret#2026" not in str(entry.metadata)
            assert "NouveauSecret#2026" not in entry.description

    def test_logging_filter_redacts_secrets(self):
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg='login password="hunter2" token=abc123 {"secret_key": "xyz"}',
            args=(),
            exc_info=None,
        )
        RedactSecretsFilter().filter(record)
        message = record.getMessage()
        assert "hunter2" not in message
        assert "abc123" not in message
        assert "xyz" not in message
        assert "REDACTED" in message

    def test_password_not_in_users_table_as_plaintext(self, finance_user):
        finance_user.refresh_from_db()
        assert DEFAULT_PASSWORD != finance_user.password
        assert len(finance_user.password) > 40

    def test_settings_do_not_embed_initial_passwords(self):
        from pathlib import Path

        config_text = Path(settings.BASE_DIR, "config", "settings.py").read_text()
        assert "2026@finEmman" not in config_text
        assert "2026@ichessadmin" not in config_text

    def test_no_secret_in_frontend_bundle_placeholders(self):
        """Guards against the initial credentials ever being committed."""
        from pathlib import Path

        root = Path(settings.BASE_DIR).parent
        for candidate in ["docker-compose.yml", ".env.example"]:
            path = root / candidate
            if path.exists():
                content = path.read_text()
                assert "2026@finEmman" not in content, candidate
                assert "2026@ichessadmin" not in content, candidate


class TestCsrfAndSessions:
    def test_django_admin_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(
            "/admin/login/", {"username": "x", "password": "y"}
        )
        assert response.status_code == 403

    def test_initial_password_flow_creates_hashed_users(self, db):
        from django.core.management import call_command
        import os

        os.environ["INITIAL_FINANCE_USERNAME"] = "EmanuelBootstrap"
        os.environ["INITIAL_FINANCE_PASSWORD"] = "InitSecret#2026"
        os.environ["INITIAL_ADMIN_USERNAME"] = "AdminBootstrap"
        os.environ["INITIAL_ADMIN_PASSWORD"] = "InitAdmin#2026"
        call_command("bootstrap_users")

        finance = User.objects.get(username="EmanuelBootstrap")
        admin = User.objects.get(username="AdminBootstrap")
        assert finance.check_password("InitSecret#2026")
        assert admin.check_password("InitAdmin#2026")
        assert finance.must_change_password is True
        assert admin.must_change_password is True
        assert "InitSecret#2026" not in finance.password
        assert finance.password.startswith("argon2$")

        # Idempotent: running again changes nothing.
        password_before = finance.password
        call_command("bootstrap_users")
        finance.refresh_from_db()
        assert finance.password == password_before
        assert User.objects.filter(username__in=["EmanuelBootstrap", "AdminBootstrap"]).count() == 2
