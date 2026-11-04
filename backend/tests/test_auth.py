"""Authentication, session and password lifecycle tests."""
from __future__ import annotations

import pytest
from django.conf import settings
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.users.models import LoginAttempt, User, UserRole

from .conftest import DEFAULT_PASSWORD

pytestmark = pytest.mark.django_db


def login(client, username, password):
    return client.post(
        "/api/auth/login/", {"username": username, "password": password}, format="json"
    )


class TestLogin:
    def test_login_success_returns_access_and_user(self, api_client, finance_user):
        response = login(api_client, "Emanuel", DEFAULT_PASSWORD)
        assert response.status_code == 200
        assert "access" in response.data
        assert response.data["user"]["username"] == "Emanuel"
        assert response.data["user"]["role"] == "FINANCE"
        # the refresh token is delivered as an httpOnly cookie, never in the body
        assert "refresh" not in response.data
        cookie = response.cookies[settings.REFRESH_COOKIE_NAME]
        assert cookie["httponly"] is True

    def test_login_is_case_insensitive_on_username(self, api_client, finance_user):
        response = login(api_client, "emanuel", DEFAULT_PASSWORD)
        assert response.status_code == 200
        assert response.data["user"]["username"] == "Emanuel"

    def test_password_hash_is_argon2(self, finance_user):
        finance_user.refresh_from_db()
        assert finance_user.password.startswith("argon2$")
        assert DEFAULT_PASSWORD not in finance_user.password

    def test_login_never_returns_password_fields(self, api_client, finance_user):
        response = login(api_client, "Emanuel", DEFAULT_PASSWORD)
        body = response.content.decode()
        assert "password" not in response.data["user"]
        assert DEFAULT_PASSWORD not in body
        assert finance_user.password not in body

    def test_wrong_password_is_rejected_and_logged(self, api_client, finance_user):
        response = login(api_client, "Emanuel", "wrong-password")
        assert response.status_code == 401
        assert LoginAttempt.objects.filter(username_attempted="Emanuel", successful=False).exists()
        finance_user.refresh_from_db()
        assert finance_user.failed_login_attempts == 1

    def test_unknown_user_generic_message(self, api_client, db):
        response = login(api_client, "ghost", "whatever")
        assert response.status_code == 401
        assert "Identifiants invalides" in response.data["detail"]

    def test_lockout_after_max_attempts(self, api_client, finance_user):
        for _ in range(settings.MAX_LOGIN_ATTEMPTS):
            login(api_client, "Emanuel", "bad-password")
        finance_user.refresh_from_db()
        assert finance_user.is_locked
        response = login(api_client, "Emanuel", DEFAULT_PASSWORD)
        assert response.status_code == 423
        assert response.data["code"] == "account_locked"

    def test_inactive_account_cannot_login(self, api_client, finance_user):
        finance_user.is_active = False
        finance_user.save(update_fields=["is_active"])
        response = login(api_client, "Emanuel", DEFAULT_PASSWORD)
        assert response.status_code == 403

    def test_missing_credentials(self, api_client, db):
        response = api_client.post("/api/auth/login/", {}, format="json")
        assert response.status_code == 400


class TestPasswordChange:
    def test_must_change_password_blocks_api(self, api_client, finance_user):
        finance_user.must_change_password = True
        finance_user.save(update_fields=["must_change_password"])
        response = login(api_client, "Emanuel", DEFAULT_PASSWORD)
        assert response.status_code == 200
        assert response.data["user"]["must_change_password"] is True
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

        # Me and change-password stay reachable, everything else is refused.
        assert api_client.get("/api/auth/me/").status_code == 200
        blocked = api_client.get("/api/finance/operations/")
        assert blocked.status_code == 403
        assert blocked.data["detail"].startswith("Vous devez changer")

    def test_change_password_clears_flag_and_revokes_old_tokens(
        self, api_client, finance_user
    ):
        first = login(api_client, "Emanuel", DEFAULT_PASSWORD)
        old_access = first.data["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {old_access}")

        response = api_client.post(
            "/api/auth/change-password/",
            {
                "current_password": DEFAULT_PASSWORD,
                "new_password": "NouveauSecret#2026",
                "confirm_password": "NouveauSecret#2026",
            },
            format="json",
        )
        assert response.status_code == 200
        finance_user.refresh_from_db()
        assert finance_user.must_change_password is False
        assert finance_user.check_password("NouveauSecret#2026")

        # Token minted before the change is rejected immediately.
        stale = APIClient()
        stale.credentials(HTTP_AUTHORIZATION=f"Bearer {old_access}")
        assert stale.get("/api/auth/me/").status_code == 401

        assert login(api_client, "Emanuel", "NouveauSecret#2026").status_code == 200

    def test_wrong_current_password_rejected(self, finance_client):
        response = finance_client.post(
            "/api/auth/change-password/",
            {
                "current_password": "faux",
                "new_password": "NouveauSecret#2026",
                "confirm_password": "NouveauSecret#2026",
            },
            format="json",
        )
        assert response.status_code == 400
        assert "current_password" in response.data

    def test_password_mismatch_rejected(self, finance_client):
        response = finance_client.post(
            "/api/auth/change-password/",
            {
                "current_password": DEFAULT_PASSWORD,
                "new_password": "NouveauSecret#2026",
                "confirm_password": "AutreSecret#2026",
            },
            format="json",
        )
        assert response.status_code == 400

    def test_weak_password_rejected(self, finance_client):
        response = finance_client.post(
            "/api/auth/change-password/",
            {
                "current_password": DEFAULT_PASSWORD,
                "new_password": "12345678",
                "confirm_password": "12345678",
            },
            format="json",
        )
        assert response.status_code == 400

    def test_password_change_is_audited(self, finance_client, finance_user):
        finance_client.post(
            "/api/auth/change-password/",
            {
                "current_password": DEFAULT_PASSWORD,
                "new_password": "NouveauSecret#2026",
                "confirm_password": "NouveauSecret#2026",
            },
            format="json",
        )
        entry = AuditLog.objects.filter(action="PASSWORD_CHANGED", actor=finance_user).first()
        assert entry is not None
        assert DEFAULT_PASSWORD not in str(entry.metadata)


class TestSession:
    def test_refresh_rotates_cookie(self, api_client, finance_user):
        response = login(api_client, "Emanuel", DEFAULT_PASSWORD)
        assert response.status_code == 200

        refreshed = api_client.post("/api/auth/refresh/")
        assert refreshed.status_code == 200
        assert "access" in refreshed.data

    def test_refresh_without_cookie_is_unauthorised(self, api_client):
        response = api_client.post("/api/auth/refresh/")
        assert response.status_code == 401
        assert response.data["code"] in {"no_session", "invalid_session"}

    def test_logout_clears_cookie(self, api_client, finance_user):
        login(api_client, "Emanuel", DEFAULT_PASSWORD)
        response = api_client.post("/api/auth/logout/")
        assert response.status_code == 200
        assert response.cookies[settings.REFRESH_COOKIE_NAME].value == ""

    def test_unauthenticated_access_refused(self, api_client):
        for url in [
            "/api/auth/me/",
            "/api/finance/operations/",
            "/api/dashboard/summary/",
            "/api/banking/status/",
            "/api/admin/users/",
        ]:
            assert api_client.get(url).status_code == 401, url

    def test_roles_endpoint_lists_two_roles(self, finance_client):
        response = finance_client.get("/api/auth/roles/")
        assert response.status_code == 200
        assert {r["value"] for r in response.data} == {"FINANCE", "ADMIN"}
        assert len(UserRole.choices) == 2
