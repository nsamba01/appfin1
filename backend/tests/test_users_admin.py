"""Administrator user-management and general-settings tests."""
from __future__ import annotations

import pytest

from apps.audit.models import AuditLog
from apps.core.models import ApplicationSettings
from apps.users.models import User, UserRole

from .conftest import DEFAULT_PASSWORD, authenticate

pytestmark = pytest.mark.django_db


class TestUserManagement:
    def test_admin_can_create_finance_user(self, admin_client):
        response = admin_client.post(
            "/api/admin/users/",
            {
                "username": "nouvelle.finance",
                "full_name": "Nouvelle Financière",
                "email": "nf@example.com",
                "role": "FINANCE",
                "password": "SolideSecret#2026",
                "force_password_change": True,
            },
            format="json",
        )
        assert response.status_code == 201, response.data
        assert response.data["role"] == "FINANCE"
        assert "password" not in response.data

        user = User.objects.get(username="nouvelle.finance")
        assert user.check_password("SolideSecret#2026")
        assert user.password.startswith("argon2$")
        assert user.must_change_password is True
        assert AuditLog.objects.filter(action="USER_CREATED", entity_id=str(user.pk)).exists()

    def test_created_finance_user_can_login(self, admin_client, api_client):
        admin_client.post(
            "/api/admin/users/",
            {
                "username": "finance2",
                "role": "FINANCE",
                "password": "SolideSecret#2026",
                "force_password_change": False,
            },
            format="json",
        )
        response = api_client.post(
            "/api/auth/login/",
            {"username": "finance2", "password": "SolideSecret#2026"},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["user"]["role"] == "FINANCE"

    def test_duplicate_username_rejected(self, admin_client, finance_user):
        response = admin_client.post(
            "/api/admin/users/",
            {"username": "Emanuel", "role": "FINANCE", "password": "SolideSecret#2026"},
            format="json",
        )
        assert response.status_code == 400
        assert "username" in response.data

    def test_weak_password_rejected_on_create(self, admin_client):
        response = admin_client.post(
            "/api/admin/users/",
            {"username": "faible", "role": "FINANCE", "password": "123456"},
            format="json",
        )
        assert response.status_code == 400

    def test_admin_can_update_user(self, admin_client, finance_user):
        response = admin_client.patch(
            f"/api/admin/users/{finance_user.pk}/",
            {"full_name": "Nom Modifié", "role": "FINANCE"},
            format="json",
        )
        assert response.status_code == 200
        finance_user.refresh_from_db()
        assert finance_user.full_name == "Nom Modifié"
        assert AuditLog.objects.filter(action="USER_UPDATED", entity_id=str(finance_user.pk)).exists()

    def test_admin_can_reset_password(self, admin_client, finance_user, api_client):
        response = admin_client.post(
            f"/api/admin/users/{finance_user.pk}/password/",
            {"new_password": "Reinitialise#2026", "force_change": True},
            format="json",
        )
        assert response.status_code == 200
        finance_user.refresh_from_db()
        assert finance_user.check_password("Reinitialise#2026")
        assert finance_user.must_change_password is True

        login = api_client.post(
            "/api/auth/login/",
            {"username": "Emanuel", "password": "Reinitialise#2026"},
            format="json",
        )
        assert login.status_code == 200
        assert login.data["user"]["must_change_password"] is True
        assert AuditLog.objects.filter(action="PASSWORD_RESET").exists()

    def test_admin_can_deactivate_and_reactivate(self, admin_client, finance_user):
        response = admin_client.post(f"/api/admin/users/{finance_user.pk}/toggle-active/")
        assert response.status_code == 200
        finance_user.refresh_from_db()
        assert finance_user.is_active is False

        response = admin_client.post(f"/api/admin/users/{finance_user.pk}/toggle-active/")
        finance_user.refresh_from_db()
        assert finance_user.is_active is True

    def test_delete_is_a_safe_deactivation(self, admin_client, finance_user):
        response = admin_client.delete(f"/api/admin/users/{finance_user.pk}/")
        assert response.status_code == 204
        finance_user.refresh_from_db()
        assert finance_user.is_active is False
        assert User.objects.filter(pk=finance_user.pk).exists()

    def test_admin_cannot_deactivate_self(self, admin_client, admin_user):
        response = admin_client.post(f"/api/admin/users/{admin_user.pk}/toggle-active/")
        assert response.status_code == 400

    def test_last_admin_cannot_be_demoted(self, admin_client, admin_user, db):
        other = User.objects.create_user(
            username="admin2", password="AutreSecret#2026", role=UserRole.ADMIN
        )
        response = admin_client.patch(
            f"/api/admin/users/{admin_user.pk}/", {"role": "FINANCE"}, format="json"
        )
        assert response.status_code == 400

        # Deleting the second admin is fine because the first stays active.
        response = admin_client.delete(f"/api/admin/users/{other.pk}/")
        assert response.status_code == 204

    def test_login_logs_visible_to_admin(self, admin_client, finance_user, api_client):
        api_client.post(
            "/api/auth/login/",
            {"username": "Emanuel", "password": "wrong"},
            format="json",
        )
        response = admin_client.get("/api/admin/login-logs/")
        assert response.status_code == 200
        assert response.data["count"] >= 1
        assert "ip_address" in response.data["results"][0]

    def test_audit_logs_visible_to_admin(self, admin_client, finance_user):
        admin_client.patch(
            f"/api/admin/users/{finance_user.pk}/", {"full_name": "X"}, format="json"
        )
        response = admin_client.get("/api/admin/audit-logs/")
        assert response.status_code == 200
        assert response.data["count"] >= 1


class TestRoleIsolation:
    def test_finance_cannot_list_users(self, finance_client):
        assert finance_client.get("/api/admin/users/").status_code == 403

    def test_finance_cannot_create_user(self, finance_client):
        response = finance_client.post(
            "/api/admin/users/",
            {"username": "pirate", "role": "ADMIN", "password": "SolideSecret#2026"},
            format="json",
        )
        assert response.status_code == 403
        assert not User.objects.filter(username="pirate").exists()

    def test_finance_cannot_read_audit_logs(self, finance_client):
        assert finance_client.get("/api/admin/audit-logs/").status_code == 403
        assert finance_client.get("/api/admin/login-logs/").status_code == 403

    def test_finance_cannot_change_settings(self, finance_client):
        assert finance_client.get("/api/admin/settings/").status_code == 403
        response = finance_client.patch(
            "/api/admin/settings/", {"currency": "EUR"}, format="json"
        )
        assert response.status_code == 403
        assert ApplicationSettings.load().currency == "USD"


class TestApplicationSettings:
    def test_admin_reads_and_updates_settings(self, admin_client):
        response = admin_client.get("/api/admin/settings/")
        assert response.status_code == 200
        response = admin_client.patch(
            "/api/admin/settings/",
            {"company_name": "ICHESS Finance SARL", "currency": "cdf"},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["currency"] == "CDF"
        assert ApplicationSettings.load().company_name == "ICHESS Finance SARL"
        assert AuditLog.objects.filter(action="SETTINGS_UPDATED").exists()

    def test_invalid_currency_rejected(self, admin_client):
        response = admin_client.patch(
            "/api/admin/settings/", {"currency": "12"}, format="json"
        )
        assert response.status_code == 400

    def test_invalid_interval_rejected(self, admin_client):
        response = admin_client.patch(
            "/api/admin/settings/", {"bank_sync_interval_minutes": 0}, format="json"
        )
        assert response.status_code == 400
