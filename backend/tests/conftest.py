from __future__ import annotations

from decimal import Decimal

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.core.models import ApplicationSettings
from apps.finance.models import Operation, OperationType
from apps.users.models import User, UserRole

DEFAULT_PASSWORD = "MotDePasse#2026"


@pytest.fixture(autouse=True)
def _clean_state(db):
    """Reset the throttle cache and ensure the settings singleton exists."""
    cache.clear()
    ApplicationSettings.load()
    yield
    cache.clear()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username="Ichessfinadmin",
        password=DEFAULT_PASSWORD,
        role=UserRole.ADMIN,
        full_name="Administrateur Test",
        is_staff=True,
        must_change_password=False,
    )


@pytest.fixture
def finance_user(db):
    return User.objects.create_user(
        username="Emanuel",
        password=DEFAULT_PASSWORD,
        role=UserRole.FINANCE,
        full_name="Financier Test",
        must_change_password=False,
    )


def authenticate(client: APIClient, user: User, password: str = DEFAULT_PASSWORD) -> APIClient:
    response = client.post(
        "/api/auth/login/", {"username": user.username, "password": password}, format="json"
    )
    assert response.status_code == 200, response.data
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    return client


@pytest.fixture
def admin_client(api_client, admin_user):
    return authenticate(api_client, admin_user)


@pytest.fixture
def finance_client(api_client, finance_user):
    return authenticate(api_client, finance_user)


@pytest.fixture
def operations(db, finance_user):
    created = []
    created.append(
        Operation.objects.create(
            date="2026-11-01",
            label="Financement reçu",
            amount=Decimal("5000.00"),
            operation_type=OperationType.ENTRY,
            created_by=finance_user,
        )
    )
    created.append(
        Operation.objects.create(
            date="2026-11-02",
            label="Achat de matériel",
            amount=Decimal("1200.00"),
            operation_type=OperationType.EXIT,
            created_by=finance_user,
        )
    )
    created.append(
        Operation.objects.create(
            date="2026-11-03",
            label="Frais de fonctionnement",
            amount=Decimal("300.00"),
            operation_type=OperationType.EXIT,
            created_by=finance_user,
        )
    )
    return created
