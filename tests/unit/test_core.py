import logging
import pytest
import sqlalchemy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.core import config, database, logging as core_logging


# ---------- config.py ----------

def test_get_bool_and_int(monkeypatch):
    monkeypatch.setenv("BOOL_TRUE", "yes")
    monkeypatch.setenv("BOOL_FALSE", "no")
    assert config._get_bool("BOOL_TRUE") is True
    assert config._get_bool("BOOL_FALSE") is False
    assert config._get_bool("MISSING", True) is True

    monkeypatch.setenv("INT_OK", "42")
    monkeypatch.setenv("INT_BAD", "oops")
    assert config._get_int("INT_OK", 1) == 42
    assert config._get_int("INT_BAD", 1) == 1


def test_compose_db_url_postgres(monkeypatch):
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_DB", "db")
    monkeypatch.setenv("POSTGRES_USER", "u")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p")
    monkeypatch.setenv("POSTGRES_PORT", "5433")
    s = config.Settings()
    assert s.DATABASE_URL.startswith("postgresql+")


def test_compose_db_url_sqlite(monkeypatch, tmp_path):
    # Supprime toutes les variables Postgres et DATABASE_URL
    for var in [
        "DATABASE_URL", "CUSTOMER_POSTGRES_HOST", "CUSTOMER_POSTGRES_DB",
        "CUSTOMER_POSTGRES_USER", "CUSTOMER_POSTGRES_PASSWORD",
        "POSTGRES_HOST", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD",
    ]:
        monkeypatch.delenv(var, raising=False)

    sqlite_file = tmp_path / "my.db"
    monkeypatch.setenv("SQLITE_PATH", str(sqlite_file))

    s = config.Settings()
    assert s.DATABASE_URL.startswith("sqlite:///")
    # Vérifie que le dossier existe
    assert sqlite_file.parent.exists()


def test_settings_defaults(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    s = config.Settings()
    assert isinstance(s.APP_NAME, str)
    assert isinstance(s.ROLE_READ, str)
    assert s.RABBITMQ_EXCHANGE_TYPE in ("topic", "fanout", "direct", "headers")


def test_settings_database_url_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/dbname")
    s = config.Settings()
    assert s.DATABASE_URL == "postgresql://u:p@host:5432/dbname"


def test_settings_keycloak_and_cors(monkeypatch):
    monkeypatch.setenv("KEYCLOAK_ISSUER", "http://kc")
    monkeypatch.delenv("KEYCLOAK_JWKS_URL", raising=False)
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "http://a.com,http://b.com")
    s = config.Settings()
    assert s.KEYCLOAK_JWKS_URL.endswith("/protocol/openid-connect/certs")
    assert "http://a.com" in s.CORS_ALLOW_ORIGINS


# ---------- database.py ----------

def test_engine_and_session():
    eng = database.engine
    assert isinstance(eng.url, sqlalchemy.engine.url.URL)
    sess = database.SessionLocal()
    sess.close()


def test_init_db(monkeypatch):
    called = {}
    monkeypatch.setattr(database.Base.metadata, "create_all", lambda bind: called.setdefault("ok", True))
    database.init_db()
    assert called["ok"] is True


def test_get_db_success_and_exception(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr(database, "SessionLocal", lambda: db)

    # cas normal
    gen = database.get_db()
    next(gen)
    with pytest.raises(StopIteration):
        gen.send(None)

    # cas exception (rollback OK)
    db.rollback = MagicMock()
    gen = database.get_db()
    next(gen)
    with pytest.raises(ValueError):
        gen.throw(ValueError("fail"))
    db.rollback.assert_called_once()


def test_get_db_rollback_and_close_fail(monkeypatch):
    fake_db = MagicMock()
    fake_db.rollback.side_effect = Exception("rollback fail")
    fake_db.close.side_effect = Exception("close fail")
    monkeypatch.setattr(database, "SessionLocal", lambda: fake_db)

    gen = database.get_db()
    next(gen)
    with pytest.raises(ValueError):
        gen.throw(ValueError("boom"))


# ---------- logging.py ----------

def test_context_filter_and_secrets_filter():
    f = core_logging.ContextFilter("svc")
    record = logging.LogRecord("n", logging.INFO, "", 1, "msg", (), None)
    assert f.filter(record)

    s = core_logging.SecretsFilter()
    record = logging.LogRecord(
        "n", logging.INFO, "", 1,
        'Authorization Bearer abc.def.ghi {"password":"x"}',
        (), None
    )
    s.filter(record)
    assert "[REDACTED]" in record.msg


def test_secrets_filter_non_str_msg():
    f = core_logging.SecretsFilter()
    record = logging.LogRecord("n", logging.INFO, "", 1, {"a": 1}, (), None)
    assert f.filter(record)


def test_json_and_plain_formatter():
    rec = logging.LogRecord("n", logging.INFO, "", 1, "hello", (), None)
    j = core_logging.JsonFormatter()
    out = j.format(rec)
    assert "hello" in out

    rec.request_id = "rid"
    rec.service = "svc"
    p = core_logging.PlainFormatter("%(message)s")
    out = p.format(rec)
    assert "hello" in out
    assert "service=svc" in out
    assert "rid=rid" in out


def test_setup_logging_plain_and_json(tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(config.settings, "LOG_FORMAT", "plain")
    monkeypatch.setattr(config.settings, "LOG_ENABLE_CONSOLE", True)

    core_logging.setup_logging()
    logger = logging.getLogger()
    assert any(isinstance(h, logging.Handler) for h in logger.handlers)

    # Appel idempotent
    core_logging.setup_logging()
    assert getattr(logger, "_configured", False) is True

    # Mode JSON sans console
    monkeypatch.setattr(config.settings, "LOG_FORMAT", "json")
    monkeypatch.setattr(config.settings, "LOG_ENABLE_CONSOLE", False)
    core_logging.setup_logging()


@pytest.mark.asyncio
async def test_access_log_middleware_success():
    class DummyRequest:
        method = "GET"
        url = SimpleNamespace(path="/x")
        client = SimpleNamespace(host="1.2.3.4")
        headers = {"user-agent": "UA"}

    async def call_next(req):
        return SimpleNamespace(status_code=200, headers={})

    resp = await core_logging.access_log_middleware(DummyRequest(), call_next)
    assert resp.headers["X-Request-ID"]
    # Après exécution, le request_id doit être reset
    assert core_logging.get_request_id() is None


@pytest.mark.asyncio
async def test_access_log_middleware_exception():
    class DummyRequest:
        method = "GET"
        url = SimpleNamespace(path="/err")
        client = SimpleNamespace(host="1.2.3.4")
        headers = {"user-agent": "UA"}

    async def call_next(req):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await core_logging.access_log_middleware(DummyRequest(), call_next)
