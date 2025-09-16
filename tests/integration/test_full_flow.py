import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.security.security import AuthContext, require_read, require_write

pytestmark = pytest.mark.acceptance

@pytest.fixture
def client_auth(client, patch_rabbitmq):
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


def test_full_customer_lifecycle(client_auth):
    # 1. Création
    payload = {
        "first_name": "Lifecycle",
        "last_name": "User",
        "email": "lifecycle@test.com",
    }
    res = client_auth.post("/customers/", json=payload)
    assert res.status_code == 201
    customer = res.json()
    customer_id = customer["id"]
    initial_version = customer["version"]

    # 2. Lecture
    res2 = client_auth.get(f"/customers/{customer_id}")
    assert res2.status_code == 200
    data = res2.json()
    assert data["first_name"] == "Lifecycle"
    assert data["last_name"] == "User"

    # 3. Mise à jour (changement de nom + ajout de company)
    update_payload = {
        "first_name": "Lifecycle",
        "last_name": "UserUpdated",
        "company": "Life Corp",
    }
    res3 = client_auth.put(
        f"/customers/{customer_id}",
        json=update_payload,
        headers={"If-Match": str(initial_version)},
    )
    assert res3.status_code == 200
    updated_customer = res3.json()
    assert updated_customer["last_name"] == "UserUpdated"
    assert updated_customer["company"] == "Life Corp"
    assert updated_customer["version"] > initial_version

    # 4. Tentative de mise à jour avec une mauvaise version (conflit)
    res4 = client_auth.put(
        f"/customers/{customer_id}",
        json={"first_name": "Conflict"},
        headers={"If-Match": str(initial_version)},  # Ancienne version
    )
    assert res4.status_code == 409

    # 5. Suppression
    res5 = client_auth.delete(f"/customers/{customer_id}")
    assert res5.status_code == 200

    # 6. Vérification de la suppression
    res6 = client_auth.get(f"/customers/{customer_id}")
    assert res6.status_code == 404
