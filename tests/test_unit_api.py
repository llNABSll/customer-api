# app/tests/test_unit_api.py
from __future__ import annotations

from types import SimpleNamespace
from fastapi import status
from app.core import rabbitmq as rabbitmq_module

# Si ton API est montée sous /api, mets "/api" ici
API_PREFIX = "/api"  # ex: "/api"

def url(path: str) -> str:
    return f"{API_PREFIX}{path}"

# -------- helpers / stubs --------

def make_client_obj(id_=1, email="john@example.com", name="John"):
    # Objet qui ressemble à ton ORM model (accès par attributs)
    return SimpleNamespace(id=id_, email=email, name=name)

# -------- tests --------

def test_create_client_success(client, monkeypatch):
    """
    POST /clients : renvoie 201 + payload, et publie un event.
    """
    # Arrange: stub repository.create_client
    from app.api import routes as customer_routes
    from app.repositories import client as repo_module

    def fake_create(db, data):
        # data est un pydantic model: on en extrait ce qu'il faut
        return make_client_obj(id_=123, email=data.email, name=getattr(data, "name", None))

    monkeypatch.setattr(repo_module, "create_client", fake_create, raising=True)

    payload = {"email": "new@example.com", "name": "New User"}
    r = client.post(url("/clients"), json=payload)
    assert r.status_code == status.HTTP_201_CREATED, r.text
    body = r.json()
    assert body["id"] == 123
    assert body["email"] == "new@example.com"

    # Vérifier qu'un event a été publié (fanout ou topic, selon ton code actuel)
    published = getattr(rabbitmq_module, "_published_events", [])
    assert any(kind in ("fanout", "topic") for kind, *_ in published), "Aucun event RabbitMQ capturé"

def test_get_client_found(client, monkeypatch):
    """
    GET /clients/{id} : 200 + client.
    """
    from app.repositories import client as repo_module

    def fake_get(db, cid):
        assert cid == 42
        return make_client_obj(id_=42, email="x@example.com", name="X")

    monkeypatch.setattr(repo_module, "get_client", fake_get, raising=True)

    r = client.get(url("/clients/42"))
    assert r.status_code == 200
    assert r.json()["email"] == "x@example.com"

def test_get_client_not_found(client, monkeypatch):
    """
    GET /clients/{id} : 404 si introuvable.
    """
    from app.repositories import client as repo_module

    def fake_get(db, cid):
        return None

    monkeypatch.setattr(repo_module, "get_client", fake_get, raising=True)

    r = client.get(url("/clients/9999"))
    assert r.status_code == 404

def test_list_clients(client, monkeypatch):
    """
    GET /clients : retourne une liste paginée.
    """
    from app.repositories import client as repo_module

    def fake_list(db, skip, limit):
        return [
            make_client_obj(id_=1, email="a@example.com"),
            make_client_obj(id_=2, email="b@example.com"),
        ][:limit]

    monkeypatch.setattr(repo_module, "get_clients", fake_list, raising=True)

    r = client.get(url("/clients?skip=0&limit=2"))
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 2

def test_update_client_ok(client, monkeypatch):
    """
    PUT /clients/{id} : 200 + client mis à jour + event publié.
    """
    from app.repositories import client as repo_module

    def fake_update(db, cid, updates):
        assert cid == 7
        return make_client_obj(id_=7, email="upd@example.com", name="UPD")

    monkeypatch.setattr(repo_module, "update_client", fake_update, raising=True)

    r = client.put(url("/clients/7"), json={"name": "UPD", "email": "upd@example.com"})
    assert r.status_code == 200
    assert r.json()["email"] == "upd@example.com"

    published = getattr(rabbitmq_module, "_published_events", [])
    assert any("updated" in str(msg) for *_kind, _ex, _rk, msg in published), "Event 'updated' non trouvé"

def test_update_client_not_found(client, monkeypatch):
    """
    PUT /clients/{id} : 404 si introuvable.
    """
    from app.repositories import client as repo_module

    def fake_update(db, cid, updates):
        return None

    monkeypatch.setattr(repo_module, "update_client", fake_update, raising=True)

    r = client.put(url("/clients/404"), json={"name": "N/A"})
    assert r.status_code == 404

def test_delete_client_ok(client, monkeypatch):
    """
    DELETE /clients/{id} : 200 + event publié.
    """
    from app.repositories import client as repo_module

    def fake_delete(db, cid):
        return True

    monkeypatch.setattr(repo_module, "delete_client", fake_delete, raising=True)

    r = client.delete(url("/clients/5"))
    assert r.status_code == 200

    published = getattr(rabbitmq_module, "_published_events", [])
    assert any("deleted" in str(msg) for *_kind, _ex, _rk, msg in published), "Event 'deleted' non trouvé"

def test_delete_client_not_found(client, monkeypatch):
    """
    DELETE /clients/{id} : 404 si introuvable.
    """
    from app.repositories import client as repo_module

    def fake_delete(db, cid):
        return False

    monkeypatch.setattr(repo_module, "delete_client", fake_delete, raising=True)

    r = client.delete(url("/clients/404"))
    assert r.status_code == 404
