import pytest
from fastapi.testclient import TestClient

import app.main


@pytest.fixture
def client(monkeypatch):
    # Patch DB et RabbitMQ pour ne pas dépendre d’une vraie infra
    monkeypatch.setattr(app.main, "engine", type("E", (), {"connect": lambda s: type("C", (), {"__enter__": lambda s: s, "__exit__": lambda *a: None, "execute": lambda s, q: 1})()})())
    monkeypatch.setattr(app.main, "init_db", lambda: None)

    async def fake_connect(): return None
    async def fake_disconnect(): return None
    monkeypatch.setattr(app.main.rabbitmq, "connect", fake_connect)
    monkeypatch.setattr(app.main.rabbitmq, "disconnect", fake_disconnect)
    monkeypatch.setattr(app.main, "start_consumer", lambda *a, **kw: None)

    return TestClient(app.main.app)


def test_health_ok(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_metrics_exposed(client):
    res = client.get("/metrics")
    assert res.status_code == 200
    assert "http_requests_total" in res.text


def test_prometheus_counter_increment(client):
    # Appel d’une route pour générer des métriques
    client.get("/health")
    res = client.get("/metrics")
    assert "http_request_duration_seconds" in res.text


def test_lifespan_runs(monkeypatch):
    called = {}

    # Patch DB
    monkeypatch.setattr(app.main, "engine", type("E", (), {"connect": lambda s: type("C", (), {"__enter__": lambda s: s, "__exit__": lambda *a: None, "execute": lambda s, q: 1})()})())
    monkeypatch.setattr(app.main, "init_db", lambda: None)

    # Patch RabbitMQ connect/disconnect
    async def fake_connect(): called["connect"] = True
    async def fake_disconnect(): called["disconnect"] = True
    monkeypatch.setattr(app.main.rabbitmq, "connect", fake_connect)
    monkeypatch.setattr(app.main.rabbitmq, "disconnect", fake_disconnect)
    monkeypatch.setattr(app.main, "start_consumer", lambda *a, **kw: None)

    with TestClient(app.main.app) as c:
        res = c.get("/health")
        assert res.status_code == 200

    # après fermeture du client → disconnect appelé
    assert "connect" in called
    assert "disconnect" in called
