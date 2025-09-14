import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock
from datetime import datetime, timezone

from app.main import app
from app.services import client_service
from app.security import security
import app.api.routes as customer_routes
from app.schemas.client import ClientResponse


@pytest.fixture
def client(patch_rabbitmq):
    mock_svc = AsyncMock(spec=client_service.CustomerService)

    fake_client = ClientResponse(
        id=1,
        first_name="Client",
        last_name="Test",
        email="client@test.com",
        company="TestCorp",
        phone="0102030405",
        version=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    mock_svc.get.return_value = fake_client
    mock_svc.list.return_value = [fake_client]
    mock_svc.get_by_email.return_value = fake_client
    mock_svc.create.return_value = fake_client
    mock_svc.update.return_value = fake_client
    mock_svc.delete.return_value = fake_client

    fake_user_context = security.AuthContext(
        user="tester",
        email="tester@example.com",
        roles=["customer:read", "customer:write"],
    )

    app.dependency_overrides = {
        customer_routes.get_customer_service: lambda: mock_svc,
        security.require_user: lambda: fake_user_context,
        security.require_read: lambda: fake_user_context,
        security.require_write: lambda: fake_user_context,
    }

    yield TestClient(app)
    app.dependency_overrides = {}


# -------------------------
# Cas ok
# -------------------------

def test_create_customer(client):
    r = client.post(
        "/customers/",
        json={"first_name": "New", "last_name": "User", "email": "new@test.com"},
    )
    assert r.status_code == 201
    mock_service = app.dependency_overrides[customer_routes.get_customer_service]()
    mock_service.create.assert_awaited()


def test_list_customers(client):
    r = client.get("/customers/")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_read_customer(client):
    r = client.get("/customers/1")
    assert r.status_code == 200
    mock_service = app.dependency_overrides[customer_routes.get_customer_service]()
    mock_service.get.assert_called_with(1)


def test_update_customer(client):
    r = client.put("/customers/1", json={"first_name": "Updated"})
    assert r.status_code == 200
    mock_service = app.dependency_overrides[customer_routes.get_customer_service]()
    mock_service.update.assert_awaited()


def test_delete_customer(client):
    r = client.delete("/customers/1")
    assert r.status_code == 200
    mock_service = app.dependency_overrides[customer_routes.get_customer_service]()
    mock_service.delete.assert_awaited()


def test_read_by_email(client):
    r = client.get("/customers/email/client@test.com")
    assert r.status_code == 200
    mock_service = app.dependency_overrides[customer_routes.get_customer_service]()
    mock_service.get_by_email.assert_called_with("client@test.com")


# -------------------------
# Cas d'erreurs
# -------------------------

def test_read_not_found(client):
    mock_service = app.dependency_overrides[customer_routes.get_customer_service]()
    mock_service.get.side_effect = client_service.NotFoundError()
    r = client.get("/customers/99")
    assert r.status_code == 404


def test_create_conflict(client):
    mock_service = app.dependency_overrides[customer_routes.get_customer_service]()
    mock_service.create.side_effect = client_service.EmailAlreadyExistsError()
    r = client.post(
        "/customers/",
        json={"first_name": "Dup", "last_name": "User", "email": "dup@test.com"},
    )
    assert r.status_code == 409


def test_update_invalid_if_match(client):
    r = client.put(
        "/customers/1",
        json={"first_name": "Updated"},
        headers={"If-Match": "abc"},
    )
    assert r.status_code == 400


def test_update_not_found(client):
    mock_service = app.dependency_overrides[customer_routes.get_customer_service]()
    mock_service.update.side_effect = client_service.NotFoundError()
    r = client.put(
        "/customers/1",
        json={"first_name": "Updated"},
        headers={"If-Match": "1"},
    )
    assert r.status_code == 404


def test_update_conflict_email(client):
    mock_service = app.dependency_overrides[customer_routes.get_customer_service]()
    mock_service.update.side_effect = client_service.EmailAlreadyExistsError()
    r = client.put(
        "/customers/1",
        json={"first_name": "Updated"},
        headers={"If-Match": "1"},
    )
    assert r.status_code == 409


def test_update_conflict_version(client):
    mock_service = app.dependency_overrides[customer_routes.get_customer_service]()
    mock_service.update.side_effect = client_service.ConcurrencyConflictError()
    r = client.put(
        "/customers/1",
        json={"first_name": "Updated"},
        headers={"If-Match": "1"},
    )
    assert r.status_code == 409


def test_delete_not_found(client):
    mock_service = app.dependency_overrides[customer_routes.get_customer_service]()
    mock_service.delete.side_effect = client_service.NotFoundError()
    r = client.delete("/customers/123")
    assert r.status_code == 404


def test_read_by_email_not_found(client):
    mock_service = app.dependency_overrides[customer_routes.get_customer_service]()
    mock_service.get_by_email.return_value = None
    r = client.get("/customers/email/missing@test.com")
    assert r.status_code == 404


# -------------------------
# Sécurité
# -------------------------

def test_forbidden_without_write_role(patch_rabbitmq):
    """Vérifie qu'un utilisateur sans rôle 'customer:write' ne peut pas créer."""
    mock_svc = AsyncMock(spec=client_service.CustomerService)

    fake_user_context = security.AuthContext(
        user="tester",
        email="tester@example.com",
        roles=["customer:read"], 
    )

    app.dependency_overrides = {
        customer_routes.get_customer_service: lambda: mock_svc,
        security.require_user: lambda: fake_user_context,
        security.require_read: lambda: fake_user_context,
    }

    test_client = TestClient(app)
    r = test_client.post(
        "/customers/", json={"first_name": "X", "last_name": "Y", "email": "x@test.com"}
    )
    assert r.status_code == 403

    app.dependency_overrides = {}
