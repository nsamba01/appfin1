"""Ecobank integration: signature, configuration, sync, error handling.

All API calls are simulated with a fake transport — no real bank is contacted.
No balance is ever invented by the application.
"""
from __future__ import annotations

import hashlib
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.banking import services as banking_services
from apps.banking.ecobank_client import (
    BalanceResult,
    EcobankApiError,
    EcobankClient,
    build_signatures,
    sha512_hex,
)
from apps.banking.models import (
    BalanceSnapshot,
    EcobankConfiguration,
    SyncLog,
    SyncStatus,
)
from apps.core.encryption import decrypt_str

pytestmark = pytest.mark.django_db

SECRET_KEY = "corp_sk_test_secret_value"
SUBSCRIPTION_KEY = "0123456789abcdef0123456789abcdef"
ACCOUNT_NO = "1441002006858"


def configure_bank(**overrides) -> EcobankConfiguration:
    config = EcobankConfiguration.load()
    config.is_enabled = overrides.pop("is_enabled", True)
    config.environment = overrides.pop("environment", "SANDBOX")
    config.base_url = "https://apimuat-gateway.ecobank.com"
    config.auth_path = "/corp-auth/api/v2/integration/auth/app/token"
    config.balance_path = (
        "/corp-account-inquiry/api/v2/integration/account/inquiry/balance"
    )
    config.client_id = "CL001"
    config.affiliate_code = "ECD"
    config.source_code = "CORP_CIB_MOBILE"
    config.public_key = "corp_pk_test"
    config.ip_address = "192.168.1.10"
    config.service_code = "ACCOUNT_SERVICE"
    config.secret_key = SECRET_KEY
    config.subscription_key = SUBSCRIPTION_KEY
    config.account_no = ACCOUNT_NO
    config.currency = "USD"
    for key, value in overrides.items():
        setattr(config, key, value)
    config.save()
    return config


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class FakeSession:
    """Records outgoing calls and replays scripted responses."""

    def __init__(self, token_response=None, balance_response=None):
        self.calls = []
        self.token_response = token_response or {
            "headerResponse": {"responseCode": "000", "responseMessage": "SUCCESS"},
            "data": {
                "access_token": "fake-access-token",
                "token_type": "Bearer",
                "expires_in": 1790783382000,
            },
        }
        self.balance_response = balance_response or {
            "headerResponse": {"responseCode": "000", "responseMessage": "SUCCESS"},
            "data": {
                "accountNo": ACCOUNT_NO,
                "accountName": "ICHESS FINANCE",
                "customerID": "479059999",
                "ccy": "USD",
                "branchCode": "H26",
                "availableBalance": 80.17,
                "currentBalance": 80.17,
                "accountClass": "CDSAIN",
                "accountStatus": "ACTIVE",
            },
        }

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        if url.endswith("/token"):
            return FakeResponse(self.token_response)
        return FakeResponse(self.balance_response)


class TestSignature:
    def test_request_token_and_secure_hash_follow_the_documented_scheme(self):
        header = "CL001" + "ECD" + "CORP_CIB_MOBILE" + "REQ123" + "GET_ACCOUNT_BALANCE" + "192.168.1.10"
        request_token, secure_hash = build_signatures(
            client_id="CL001",
            affiliate_code="ECD",
            source_code="CORP_CIB_MOBILE",
            request_id="REQ123",
            request_type="GET_ACCOUNT_BALANCE",
            ip_address="192.168.1.10",
            secret_key=SECRET_KEY,
            endpoint_fields=ACCOUNT_NO,
        )
        expected_token = hashlib.sha512((header + SECRET_KEY).encode()).hexdigest()
        expected_hash = hashlib.sha512(
            (header + expected_token + ACCOUNT_NO + SECRET_KEY).encode()
        ).hexdigest()
        assert request_token == expected_token
        assert secure_hash == expected_hash
        assert len(secure_hash) == 128
        assert sha512_hex("abc") == hashlib.sha512(b"abc").hexdigest()

    def test_hash_order_differs_from_json_order(self):
        """A valid digest must not use the JSON body field order (affiliate first)."""
        wrong_header = "ECD" + "CL001" + "CORP_CIB_MOBILE" + "REQ123" + "GET_ACCOUNT_BALANCE" + "192.168.1.10"
        correct, _ = build_signatures(
            client_id="CL001",
            affiliate_code="ECD",
            source_code="CORP_CIB_MOBILE",
            request_id="REQ123",
            request_type="GET_ACCOUNT_BALANCE",
            ip_address="192.168.1.10",
            secret_key=SECRET_KEY,
            endpoint_fields=ACCOUNT_NO,
        )
        wrong = sha512_hex(wrong_header + SECRET_KEY)
        assert correct != wrong


class TestClientTransport:
    def test_balance_request_contains_required_fields_and_headers(self):
        config = configure_bank()
        session = FakeSession()
        client = EcobankClient(config, session=session)
        result = client.get_balance()

        assert result.available_balance == Decimal("80.17")
        assert result.currency == "USD"
        assert result.account_no == ACCOUNT_NO

        token_call, balance_call = session.calls[0], session.calls[1]
        assert token_call["json"]["serviceCode"] == "ACCOUNT_SERVICE"
        assert token_call["json"]["headerRequest"]["requestType"] == "GET_API_TOKEN"
        assert token_call["headers"]["Ocp-Apim-Subscription-Key"] == SUBSCRIPTION_KEY

        body = balance_call["json"]
        assert body["accountNo"] == ACCOUNT_NO
        assert body["headerRequest"]["requestType"] == "GET_ACCOUNT_BALANCE"
        assert body["headerRequest"]["affiliateCode"] == "ECD"
        assert set(body["headerRequest"]) == {
            "affiliateCode",
            "clientId",
            "sourceCode",
            "requestId",
            "ipAddress",
            "requestType",
            "requestToken",
        }
        assert "secureHash" in body
        assert balance_call["headers"]["Authorization"] == "Bearer fake-access-token"

    def test_authentication_failure_raises(self):
        config = configure_bank()
        session = FakeSession(
            token_response={
                "headerResponse": {
                    "responseCode": "999",
                    "responseMessage": "FAILED",
                    "responseDesc": "Invalid SecureHash or Request Token Provided",
                },
                "data": {},
            }
        )
        client = EcobankClient(config, session=session)
        with pytest.raises(Exception) as exc:
            client.get_balance()
        assert "Invalid SecureHash" in str(exc.value)

    def test_api_refusal_on_balance_raises(self):
        config = configure_bank()
        session = FakeSession(
            balance_response={
                "headerResponse": {
                    "responseCode": "999",
                    "responseDesc": "No record Found",
                },
                "data": {},
            }
        )
        client = EcobankClient(config, session=session)
        with pytest.raises(EcobankApiError):
            client.get_balance()

    def test_missing_credentials_raise_configuration_error(self):
        config = EcobankConfiguration.load()
        client = EcobankClient(config, session=FakeSession())
        with pytest.raises(Exception) as exc:
            client.get_balance()
        assert "Configuration Ecobank incomplète" in str(exc.value)


class TestConfigurationApi:
    def test_admin_updates_config_and_secrets_are_never_returned(self, admin_client):
        response = admin_client.patch(
            "/api/banking/config/",
            {
                "is_enabled": True,
                "environment": "SANDBOX",
                "base_url": "https://apimuat-gateway.ecobank.com",
                "auth_path": "/corp-auth/api/v2/integration/auth/app/token",
                "balance_path": "/corp-account-inquiry/api/v2/integration/account/inquiry/balance",
                "client_id": "CL001",
                "affiliate_code": "ECD",
                "source_code": "CORP_CIB_MOBILE",
                "public_key": "corp_pk_test",
                "ip_address": "192.168.1.10",
                "secret_key": SECRET_KEY,
                "subscription_key": SUBSCRIPTION_KEY,
                "account_no": ACCOUNT_NO,
                "currency": "USD",
            },
            format="json",
        )
        assert response.status_code == 200, response.data
        body = response.content.decode()
        assert SECRET_KEY not in body
        assert SUBSCRIPTION_KEY not in body
        assert ACCOUNT_NO not in body
        assert response.data["has_secret_key"] is True
        assert response.data["masked_account_no"].endswith("6858")
        assert "•" in response.data["masked_account_no"]

        config = EcobankConfiguration.load()
        stored = config.secret_key_encrypted
        assert SECRET_KEY not in stored
        assert decrypt_str(stored) == SECRET_KEY
        assert config.account_no == ACCOUNT_NO

    def test_secret_is_not_overwritten_when_omitted(self, admin_client):
        configure_bank()
        response = admin_client.patch(
            "/api/banking/config/", {"client_id": "CL002"}, format="json"
        )
        assert response.status_code == 200
        config = EcobankConfiguration.load()
        assert config.secret_key == SECRET_KEY
        assert config.client_id == "CL002"

    def test_http_base_url_rejected(self, admin_client):
        response = admin_client.patch(
            "/api/banking/config/", {"base_url": "http://insecure.example.com"}, format="json"
        )
        assert response.status_code == 400

    def test_production_rejects_uat_url(self, admin_client):
        response = admin_client.patch(
            "/api/banking/config/",
            {"environment": "PRODUCTION", "base_url": "https://artxuat.ecobank.com"},
            format="json",
        )
        assert response.status_code == 400

    def test_finance_cannot_read_or_write_config(self, finance_client):
        assert finance_client.get("/api/banking/config/").status_code == 403
        response = finance_client.patch(
            "/api/banking/config/", {"is_enabled": False}, format="json"
        )
        assert response.status_code == 403

    def test_finance_cannot_trigger_sync(self, finance_client):
        assert finance_client.post("/api/banking/sync/").status_code == 403

    def test_finance_cannot_read_sync_logs(self, finance_client):
        assert finance_client.get("/api/banking/logs/").status_code == 403


class TestSync:
    def test_successful_sync_creates_snapshot_and_log(self, monkeypatch, admin_client):
        configure_bank()

        def fake_get_balance(self, **kwargs):
            return BalanceResult(
                account_no=ACCOUNT_NO,
                account_name="ICHESS FINANCE",
                currency="USD",
                available_balance=Decimal("80.17"),
                current_balance=Decimal("80.17"),
                account_status="ACTIVE",
                request_id="REQ123",
            )

        monkeypatch.setattr(EcobankClient, "get_balance", fake_get_balance)
        response = admin_client.post("/api/banking/sync/")
        assert response.status_code == 200, response.data
        assert response.data["success"] is True
        assert response.data["bank"]["available_balance"] == "80.17"
        assert response.data["bank"]["is_sandbox"] is False
        assert BalanceSnapshot.objects.filter(is_sandbox=False).count() == 1
        assert SyncLog.objects.filter(status=SyncStatus.SUCCESS).exists()
        config = EcobankConfiguration.load()
        assert config.last_sync_status == SyncStatus.SUCCESS
        assert config.currency == "USD"

    def test_failed_sync_records_error_and_no_fake_balance(self, monkeypatch, admin_client):
        configure_bank()

        def boom(self, **kwargs):
            raise EcobankApiError(
                "Ecobank a refusé la requête : Invalid SecureHash or Request Token Provided",
                http_status=200,
                response_code="999",
            )

        monkeypatch.setattr(EcobankClient, "get_balance", boom)
        response = admin_client.post("/api/banking/sync/")
        assert response.status_code == 502
        assert response.data["success"] is False
        assert BalanceSnapshot.objects.count() == 0
        log = SyncLog.objects.get(status=SyncStatus.FAILED)
        assert "Invalid SecureHash" in log.message
        assert EcobankConfiguration.load().last_sync_status == SyncStatus.FAILED

    def test_previous_balance_preserved_after_failure(self, monkeypatch, admin_client):
        configure_bank()
        BalanceSnapshot.objects.create(
            status=SyncStatus.SUCCESS,
            source=BalanceSnapshot.Source.API,
            available_balance=Decimal("500.00"),
            currency="USD",
            account_no_masked="••••••6858",
        )

        def boom(self, **kwargs):
            raise EcobankApiError("Panne réseau", http_status=None)

        monkeypatch.setattr(EcobankClient, "get_balance", boom)
        admin_client.post("/api/banking/sync/")
        status_response = admin_client.get("/api/banking/status/")
        assert status_response.data["bank"]["available_balance"] == "500.00"

    def test_sync_skipped_when_not_configured(self, admin_client):
        response = admin_client.post("/api/banking/sync/")
        assert response.data["success"] is False
        assert BalanceSnapshot.objects.count() == 0
        assert SyncLog.objects.filter(status=SyncStatus.SKIPPED).exists()

    def test_scheduled_sync_respects_interval(self, monkeypatch, admin_client):
        config = configure_bank()
        BalanceSnapshot.objects.create(
            status=SyncStatus.SUCCESS,
            source=BalanceSnapshot.Source.API,
            available_balance=Decimal("10.00"),
            currency="USD",
            fetched_at=timezone.now(),
        )
        outcome = banking_services.perform_sync(trigger="SCHEDULED")
        assert outcome.success is False
        assert "intervalle" in outcome.message.lower()

    def test_sandbox_mode_is_clearly_flagged(self, admin_client):
        config = EcobankConfiguration.load()
        config.sandbox_mode_enabled = True
        config.is_enabled = True
        config.save()
        response = admin_client.post("/api/banking/sync/")
        assert response.status_code == 200
        assert response.data["success"] is True
        snapshot = BalanceSnapshot.objects.get()
        assert snapshot.is_sandbox is True
        assert snapshot.source == BalanceSnapshot.Source.SANDBOX

        status_response = admin_client.get("/api/banking/status/")
        assert status_response.data["bank"]["is_sandbox"] is True
        summary = admin_client.get("/api/dashboard/summary/")
        assert any("sandbox" in alert["title"].lower() for alert in summary.data["alerts"])
        # A simulated balance must never be used for a real reconciliation.
        assert summary.data["comparison"]["status"] == "UNAVAILABLE"
        assert summary.data["comparison"]["has_real_bank_data"] is False

    def test_sync_history_endpoint(self, monkeypatch, admin_client):
        configure_bank()

        def fake_get_balance(self, **kwargs):
            return BalanceResult(
                account_no=ACCOUNT_NO,
                account_name="ICHESS FINANCE",
                currency="USD",
                available_balance=Decimal("250.00"),
                current_balance=None,
                account_status="ACTIVE",
            )

        monkeypatch.setattr(EcobankClient, "get_balance", fake_get_balance)
        admin_client.post("/api/banking/sync/")
        response = admin_client.get("/api/banking/history/")
        assert response.status_code == 200
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["available_balance"] == "250.00"


class TestBankingStatus:
    def test_status_available_to_finance_without_secrets(self, finance_client):
        configure_bank()
        response = finance_client.get("/api/banking/status/")
        assert response.status_code == 200
        bank = response.data["bank"]
        assert bank["name"] == "Ecobank"
        assert bank["available_balance"] is None
        assert bank["connection_status"] in {"CONFIGURED", "CONNECTED", "NOT_CONFIGURED"}
        body = response.content.decode()
        assert SECRET_KEY not in body
        assert SUBSCRIPTION_KEY not in body
        assert ACCOUNT_NO not in body

    def test_status_when_not_configured(self, finance_client):
        response = finance_client.get("/api/banking/status/")
        assert response.status_code == 200
        assert response.data["bank"]["connection_status"] == "NOT_CONFIGURED"
        assert response.data["bank"]["available_balance"] is None

    def test_connection_test_records_result(self, monkeypatch, admin_client):
        configure_bank()
        monkeypatch.setattr(
            EcobankClient,
            "test_connection",
            lambda self: {"status": "CONNECTED", "message": "OK", "duration_ms": 5},
        )
        response = admin_client.post("/api/banking/config/test/")
        assert response.status_code == 200
        assert response.data["success"] is True
        config = EcobankConfiguration.load()
        assert config.last_test_status == "CONNECTED"
        assert config.last_test_at is not None

    def test_connection_test_failure_is_reported(self, monkeypatch, admin_client):
        configure_bank()

        def boom(self):
            raise EcobankApiError("Accès refusé par la passerelle Ecobank.")

        monkeypatch.setattr(EcobankClient, "test_connection", boom)
        response = admin_client.post("/api/banking/config/test/")
        assert response.status_code == 200
        assert response.data["success"] is False
        assert "refusé" in response.data["message"]

    def test_connection_test_requires_credentials(self, admin_client):
        response = admin_client.post("/api/banking/config/test/")
        assert response.status_code == 400

    def test_clear_secrets(self, admin_client):
        configure_bank()
        response = admin_client.post("/api/banking/config/clear-secrets/")
        assert response.status_code == 200
        config = EcobankConfiguration.load()
        assert config.secret_key_encrypted == ""
        assert config.account_no_encrypted == ""
        assert config.is_enabled is False
