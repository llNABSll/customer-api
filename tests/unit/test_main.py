import pytest
from fastapi.testclient import TestClient

import app.main


@pytest.fixture
def client(monkeypatch):
    # Patch DB et RabbitMQ pour ne pas dépendre d’une vraie infra
    monkeypatch.setattr(
        app.main,
        "engine",
        type(
            "E",
            (),
            {"connect": lambda s: type("C", (), {"__enter__": lambda s: s, "__exit__": lambda *a: None, "execute": lambda s, q: 1})()},
        )(),
    )
    monkeypatch.setattr(app.main, "init_db", lambda: None)

    async def fake_connect(): return None
    async def fake_disconnect(): return None
    monkeypatch.setattr(app.main.rabbitmq, "connect", fake_connect)
    monkeypatch.setattr(app.main.rabbitmq, "disconnect", fake_disconnect)
    monkeypatch.setattr(app.main, "start_consumer", lambda *a, **kw: None)

    return TestClient(app.main.app)


# ---------- health / metrics ----------

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


# ---------- lifespan ----------

def test_lifespan_runs(monkeypatch):
    called = {}

    # Patch DB
    monkeypatch.setattr(
        app.main,
        "engine",
        type(
            "E",
            (),
            {"connect": lambda s: type("C", (), {"__enter__": lambda s: s, "__exit__": lambda *a: None, "execute": lambda s, q: 1})()},
        )(),
    )
    monkeypatch.setattr(app.main, "init_db", lambda: None)

    async def fake_connect(): called["connect"] = True
    async def fake_disconnect(): called["disconnect"] = True
    monkeypatch.setattr(app.main.rabbitmq, "connect", fake_connect)
    monkeypatch.setattr(app.main.rabbitmq, "disconnect", fake_disconnect)
    monkeypatch.setattr(app.main, "start_consumer", lambda *a, **kw: None)

    with TestClient(app.main.app) as c:
        res = c.get("/health")
        assert res.status_code == 200

    assert "connect" in called
    assert "disconnect" in called


def test_lifespan_db_and_rabbitmq_fail(monkeypatch, caplog):
    monkeypatch.setattr(app.main, "engine", type("E", (), {"connect": lambda s: (_ for _ in ()).throw(Exception("db fail"))})())
    monkeypatch.setattr(app.main, "init_db", lambda: (_ for _ in ()).throw(Exception("init fail")))

    async def bad_connect(): raise Exception("rabbit fail")
    async def bad_disconnect(): raise Exception("rabbit disco fail")

    monkeypatch.setattr(app.main.rabbitmq, "connect", bad_connect)
    monkeypatch.setattr(app.main.rabbitmq, "disconnect", bad_disconnect)
    monkeypatch.setattr(app.main, "start_consumer", lambda *a, **kw: None)

    caplog.set_level("ERROR")
    with TestClient(app.main.app) as c:
        c.get("/health")

    assert "database connectivity check failed" in caplog.text
    assert "database init failed" in caplog.text
    assert "Échec initialisation RabbitMQ" in caplog.text


# ---------- metrics middleware ----------

def test_metrics_middleware_customers_routes(monkeypatch):
    # Patch DB + RabbitMQ minimal
    monkeypatch.setattr(app.main, "init_db", lambda: None)
    monkeypatch.setattr(app.main.rabbitmq, "connect", lambda: None)
    monkeypatch.setattr(app.main.rabbitmq, "disconnect", lambda: None)
    monkeypatch.setattr(app.main, "start_consumer", lambda *a, **kw: None)

    with TestClient(app.main.app) as client:
        # Route sans ID
        client.get("/customers")
        # Route avec ID
        client.get("/customers/123")

        res = client.get("/metrics")
        body = res.text
        assert "/customers" in body
        assert "/customers/{id}" in body


# ---------- CORS ----------

def test_cors_headers(client):
    res = client.options(
        "/customers",
        headers={
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" in res.headers
