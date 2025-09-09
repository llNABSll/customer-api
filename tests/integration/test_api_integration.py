# tests/integration/test_api.py
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.security.security import AuthContext, require_read, require_write

# Utilise le client fixture de conftest.py qui fournit une DB propre
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
    payload = {"name": "John Doe", "email": "john.doe@test.com", "company": "Doe Corp"}
    res_create = client_auth.post("/customers/", json=payload)
    assert res_create.status_code == 201
    created_customer = res_create.json()
    assert created_customer["email"] == "john.doe@test.com"

    res_get = client_auth.get(f"/customers/{created_customer['id']}")
    assert res_get.status_code == 200
    assert res_get.json()["name"] == "John Doe"

def test_conflict_on_duplicate_email(client_auth):
    payload = {"name": "Jane Doe", "email": "jane.doe@test.com"}
    client_auth.post("/customers/", json=payload)
    res_conflict = client_auth.post("/customers/", json=payload)
    assert res_conflict.status_code == 409

def test_list_and_filters(client_auth):
    client_auth.post("/customers/", json={"name": "Alice", "email": "alice@test.com", "company": "A Corp"})
    client_auth.post("/customers/", json={"name": "Bob", "email": "bob@test.com", "company": "B Corp"})
    
    res = client_auth.get("/customers/?company=A Corp")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["name"] == "Alice"
