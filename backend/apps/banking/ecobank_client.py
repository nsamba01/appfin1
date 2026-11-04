"""
Ecobank API client.

Protocol implemented strictly from Ecobank's published Account Enquiry
documentation and the observable behaviour of the UAT gateway:

  Gateway base URL        https://apimuat-gateway.ecobank.com
  Token endpoint (POST)   /corp-auth/api/v2/integration/auth/app/token
  Balance endpoint (POST) /corp-account-inquiry/api/v2/integration/account/inquiry/balance

Every request carries two independent credentials:
  Ocp-Apim-Subscription-Key: <subscription key from the developer portal>
  Authorization: Bearer <token minted for the ACCOUNT_SERVICE service code>

Signature (SHA-512, lower-case hex, secret concatenated — NOT an HMAC):

  HEADER       = clientId + affiliateCode + sourceCode + requestId + requestType + ipAddress
  requestToken = SHA512(HEADER + secretKey)
  secureHash   = SHA512(HEADER + requestToken + <endpoint fields> + secretKey)

  token   endpoint fields: publicKey, serviceCode
  balance endpoint fields: accountNo

The outcome is carried by headerResponse.responseCode ("000" = success) and not
by the HTTP status, which is 200 even for refused requests.

Endpoints, paths and field names are configurable in the admin UI because they
differ between environments; no endpoint or credential is invented here.
"""
from __future__ import annotations

import hashlib
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal

import requests
from django.conf import settings
from django.utils import timezone

from apps.core.utils import mask_account_number, to_decimal

from .models import ApiTokenCache, BankEnvironment, EcobankConfiguration

logger = logging.getLogger("apps.banking.ecobank")

SUCCESS_CODE = "000"


class EcobankError(Exception):
    """Base class for all Ecobank integration errors."""

    code = "ECOBANK_ERROR"
    http_status: int | None = None

    def __init__(self, message: str, *, http_status: int | None = None, response_code: str = ""):
        super().__init__(message)
        self.message = message
        self.http_status = http_status
        self.response_code = response_code


class ConfigurationError(EcobankError):
    code = "NOT_CONFIGURED"


class EcobankAuthError(EcobankError):
    code = "AUTH_FAILED"


class EcobankApiError(EcobankError):
    code = "API_ERROR"


class EcobankNetworkError(EcobankError):
    code = "NETWORK_ERROR"


class InvalidResponseError(EcobankError):
    code = "INVALID_RESPONSE"


@dataclass
class BalanceResult:
    account_no: str
    account_name: str
    currency: str
    available_balance: Decimal
    current_balance: Decimal | None
    account_status: str
    branch_code: str = ""
    request_id: str = ""
    response_code: str = SUCCESS_CODE
    raw: dict = field(default_factory=dict)

    @property
    def masked_account_no(self) -> str:
        return mask_account_number(self.account_no)


def sha512_hex(value: str) -> str:
    return hashlib.sha512(value.encode("utf-8")).hexdigest()


def build_header_string(
    *, client_id: str, affiliate_code: str, source_code: str, request_id: str,
    request_type: str, ip_address: str
) -> str:
    """Hashed field order differs from the JSON body order."""
    return "".join([client_id, affiliate_code, source_code, request_id, request_type, ip_address])


def build_signatures(
    *,
    client_id: str,
    affiliate_code: str,
    source_code: str,
    request_id: str,
    request_type: str,
    ip_address: str,
    secret_key: str,
    endpoint_fields: str = "",
) -> tuple[str, str]:
    """Return (request_token, secure_hash)."""
    header = build_header_string(
        client_id=client_id,
        affiliate_code=affiliate_code,
        source_code=source_code,
        request_id=request_id,
        request_type=request_type,
        ip_address=ip_address,
    )
    request_token = sha512_hex(header + secret_key)
    secure_hash = sha512_hex(header + request_token + endpoint_fields + secret_key)
    return request_token, secure_hash


def new_request_id() -> str:
    return uuid.uuid4().hex[:20].upper()


class EcobankClient:
    """Stateless client — configuration is passed in for testability."""

    def __init__(self, config: EcobankConfiguration, session: requests.Session | None = None):
        self.config = config
        self.session = session or requests.Session()
        self.timeout = max(5, int(config.timeout_seconds or settings.ECOBANK_HTTP_TIMEOUT))

    # -- helpers -----------------------------------------------------------
    def _url(self, path: str) -> str:
        base = (self.config.base_url or "").rstrip("/")
        path = (path or "").strip()
        if not path.startswith("/"):
            path = "/" + path
        return f"{base}{path}"

    def _assert_configured(self) -> None:
        if not self.config.has_credentials:
            missing = []
            if not self.config.base_url:
                missing.append("URL de l'API")
            if not self.config.client_id:
                missing.append("Client ID")
            if not self.config.affiliate_code:
                missing.append("Affiliate Code")
            if not self.config.source_code:
                missing.append("Source Code")
            if not self.config.public_key:
                missing.append("Public Key")
            if not self.config.has_secret_key:
                missing.append("Secret Key")
            if not self.config.has_subscription_key:
                missing.append("Subscription Key")
            if not self.config.has_account_no:
                missing.append("Numéro de compte")
            if not self.config.ip_address:
                missing.append("Adresse IP déclarée")
            raise ConfigurationError(
                "Configuration Ecobank incomplète : " + ", ".join(missing)
            )

    def _headers(self, token: str | None = None) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Cache-Control": "no-cache",
            "Ocp-Apim-Subscription-Key": self.config.subscription_key,
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    @staticmethod
    def _request_id_header(rid: str) -> dict:
        return {"X-Request-Id": rid}

    def _token_cache_key(self) -> str:
        identity = f"{self.config.base_url}|{self.config.client_id}|{self.config.source_code}|{self.config.service_code}|{self.config.environment}"
        return hashlib.sha256(identity.encode()).hexdigest()

    # -- token -------------------------------------------------------------
    def get_access_token(self, force: bool = False) -> str:
        self._assert_configured()
        cache_key = self._token_cache_key()
        if not force:
            cached = ApiTokenCache.get_valid(cache_key)
            if cached:
                return cached

        request_id = new_request_id()
        request_type = self.config.token_request_type or "GET_API_TOKEN"
        endpoint_fields = f"{self.config.public_key}{self.config.service_code}"
        request_token, secure_hash = build_signatures(
            client_id=self.config.client_id,
            affiliate_code=self.config.affiliate_code,
            source_code=self.config.source_code,
            request_id=request_id,
            request_type=request_type,
            ip_address=str(self.config.ip_address),
            secret_key=self.config.secret_key,
            endpoint_fields=endpoint_fields,
        )
        payload = {
            "headerRequest": {
                "affiliateCode": self.config.affiliate_code,
                "clientId": self.config.client_id,
                "sourceCode": self.config.source_code,
                "requestId": request_id,
                "ipAddress": str(self.config.ip_address),
                "requestType": request_type,
                "requestToken": request_token,
            },
            "publicKey": self.config.public_key,
            "serviceCode": self.config.service_code,
            "secureHash": secure_hash,
        }

        data, http_status = self._post(self.config.auth_path, payload, token=None)
        header = data.get("headerResponse") or {}
        response_code = str(header.get("responseCode", ""))
        if response_code != SUCCESS_CODE:
            raise EcobankAuthError(
                "Échec de l'authentification Ecobank : "
                + (header.get("responseDesc") or header.get("responseMessage") or "réponse inattendue"),
                http_status=http_status,
                response_code=response_code,
            )
        token_data = data.get("data") or {}
        access_token = token_data.get("access_token") or token_data.get("accessToken")
        if not access_token:
            raise InvalidResponseError(
                "La réponse d'authentification ne contient pas d'access_token.",
                http_status=http_status,
            )

        expires_at = self._compute_expiry(token_data.get("expires_in"))
        ApiTokenCache.store(cache_key, access_token, expires_at)
        logger.info(
            "Ecobank token obtained (env=%s code=%s expires_at=%s)",
            self.config.environment,
            response_code,
            expires_at.isoformat(),
        )
        return access_token

    @staticmethod
    def _compute_expiry(raw) -> datetime:
        """expires_in is observed as an absolute millisecond timestamp.

        We handle both forms defensively: if the value looks like an epoch
        (ms or s) we use it; otherwise we treat it as a duration in seconds,
        capped to a sane maximum.
        """
        now = timezone.now()
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return now + timedelta(minutes=5)
        if value > 1e11:  # milliseconds epoch
            dt = datetime.fromtimestamp(value / 1000, tz=dt_timezone.utc)
            if dt > now:
                return min(dt, now + timedelta(hours=12))
            return now + timedelta(minutes=5)
        if value > 1e9:  # seconds epoch
            dt = datetime.fromtimestamp(value, tz=dt_timezone.utc)
            if dt > now:
                return min(dt, now + timedelta(hours=12))
            return now + timedelta(minutes=5)
        seconds = max(60.0, min(value, 12 * 3600))
        return now + timedelta(seconds=seconds)

    # -- balance -----------------------------------------------------------
    def get_balance(self, *, force_new_token: bool = False) -> BalanceResult:
        self._assert_configured()
        token = self.get_access_token(force=force_new_token)
        request_id = new_request_id()
        request_type = self.config.balance_request_type or "GET_ACCOUNT_BALANCE"
        account_no = self.config.account_no
        endpoint_fields = account_no
        request_token, secure_hash = build_signatures(
            client_id=self.config.client_id,
            affiliate_code=self.config.affiliate_code,
            source_code=self.config.source_code,
            request_id=request_id,
            request_type=request_type,
            ip_address=str(self.config.ip_address),
            secret_key=self.config.secret_key,
            endpoint_fields=endpoint_fields,
        )
        payload = {
            "headerRequest": {
                "affiliateCode": self.config.affiliate_code,
                "clientId": self.config.client_id,
                "sourceCode": self.config.source_code,
                "requestId": request_id,
                "ipAddress": str(self.config.ip_address),
                "requestType": request_type,
                "requestToken": request_token,
            },
            "secureHash": secure_hash,
            "accountNo": account_no,
        }

        data, http_status = self._post(self.config.balance_path, payload, token=token)
        header = data.get("headerResponse") or {}
        response_code = str(header.get("responseCode", ""))
        if response_code in {"403"}:
            # Expired/invalid token: renew once and retry (documented behaviour).
            token = self.get_access_token(force=True)
            data, http_status = self._post(self.config.balance_path, payload, token=token)
            header = data.get("headerResponse") or {}
            response_code = str(header.get("responseCode", ""))

        if response_code != SUCCESS_CODE:
            raise EcobankApiError(
                "Ecobank a refusé la requête : "
                + (header.get("responseDesc") or header.get("responseMessage") or "erreur API"),
                http_status=http_status,
                response_code=response_code,
            )

        body = data.get("data") or {}
        if not body:
            raise InvalidResponseError(
                "La réponse Ecobank ne contient aucune donnée de compte.",
                http_status=http_status,
                response_code=response_code,
            )

        available_raw = body.get("availableBalance")
        current_raw = body.get("currentBalance")
        if available_raw is None and current_raw is None:
            raise InvalidResponseError(
                "La réponse Ecobank ne contient aucun solde exploitable.",
                http_status=http_status,
                response_code=response_code,
            )

        return BalanceResult(
            account_no=str(body.get("accountNo") or account_no),
            account_name=str(body.get("accountName") or ""),
            currency=str(body.get("ccy") or ""),
            available_balance=to_decimal(
                available_raw if available_raw is not None else current_raw
            ),
            current_balance=to_decimal(current_raw) if current_raw is not None else None,
            account_status=str(body.get("accountStatus") or ""),
            branch_code=str(body.get("branchCode") or ""),
            request_id=request_id,
            response_code=response_code,
            raw={
                "accountClass": body.get("accountClass"),
                "customerID": body.get("customerID"),
                "branchCode": body.get("branchCode"),
            },
        )

    # -- transport ---------------------------------------------------------
    def _post(self, path: str, payload: dict, token: str | None) -> tuple[dict, int]:
        url = self._url(path)
        started = time.monotonic()
        try:
            response = self.session.post(
                url, json=payload, headers=self._headers(token), timeout=self.timeout
            )
        except requests.Timeout as exc:
            raise EcobankNetworkError(
                f"Délai dépassé ({self.timeout}s) lors de l'appel à Ecobank."
            ) from exc
        except requests.RequestException as exc:
            logger.warning("Ecobank network error: %s", exc.__class__.__name__)
            raise EcobankNetworkError(
                "Impossible de joindre l'API Ecobank. Vérifiez l'URL et la connectivité réseau."
            ) from exc
        finally:
            logger.debug(
                "Ecobank POST %s finished in %.0fms", path, (time.monotonic() - started) * 1000
            )

        try:
            data = response.json()
        except ValueError:
            raise InvalidResponseError(
                f"Réponse non-JSON de l'API Ecobank (HTTP {response.status_code}).",
                http_status=response.status_code,
            )

        if not isinstance(data, dict):
            raise InvalidResponseError(
                "Format de réponse Ecobank inattendu.", http_status=response.status_code
            )

        if response.status_code >= 500:
            header = data.get("headerResponse") or {}
            raise EcobankApiError(
                "Erreur interne de l'API Ecobank (HTTP %s)." % response.status_code,
                http_status=response.status_code,
                response_code=str(header.get("responseCode", "")),
            )
        if response.status_code in {401, 403} and not data.get("headerResponse"):
            raise EcobankAuthError(
                "Accès refusé par la passerelle Ecobank (vérifiez la clé d'abonnement).",
                http_status=response.status_code,
            )
        return data, response.status_code

    def test_connection(self) -> dict:
        """Request a token only — proves credentials without touching balances."""
        started = time.monotonic()
        token = self.get_access_token(force=True)
        elapsed = int((time.monotonic() - started) * 1000)
        return {
            "status": "CONNECTED",
            "message": "Authentification Ecobank réussie (jeton obtenu).",
            "duration_ms": elapsed,
            "token_received": bool(token),
            "environment": self.config.environment,
        }

    def is_production(self) -> bool:
        return self.config.environment == BankEnvironment.PRODUCTION
