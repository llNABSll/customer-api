import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.security.security import AuthContext, require_read, require_write


@pytest.fixture
def client_auth(client, patch_rabbitmq):
    # Mock Security Dependencies
    fake_ctx = AuthContext(
        user="test-user",
        email="test@example.com",
        roles=["customer:read", "customer:write"],
    )
    app.dependency_overrides[require_read] = lambda: fake_ctx
    app.dependency_overrides[require_write] = lambda: fake_ctx

    yield client

    del app.dependency_overrides[require_read]
    del app.dependency_overrides[require_write]


def test_create_and_get_customer(client_auth):
    payload = {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@test.com",
        "company": "Doe Corp",
    }
    res_create = client_auth.post("/customers/", json=payload)
    assert res_create.status_code == 201
    created_customer = res_create.json()
    assert created_customer["email"] == "john.doe@test.com"

    res_get = client_auth.get(f"/customers/{created_customer['id']}")
    assert res_get.status_code == 200
    data = res_get.json()
    assert data["first_name"] == "John"
    assert data["last_name"] == "Doe"


def test_conflict_on_duplicate_email(client_auth):
    payload = {
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "jane.doe@test.com",
    }
    client_auth.post("/customers/", json=payload)
    res_conflict = client_auth.post("/customers/", json=payload)
    assert res_conflict.status_code == 409


def test_list_and_filters(client_auth):
    client_auth.post(
        "/customers/",
        json={"first_name": "Alice", "last_name": "A", "email": "alice@test.com", "company": "A Corp"},
    )
    client_auth.post(
        "/customers/",
        json={"first_name": "Bob", "last_name": "B", "email": "bob@test.com", "company": "B Corp"},
    )

    res = client_auth.get("/customers/?company=A Corp")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["first_name"] == "Alice"
