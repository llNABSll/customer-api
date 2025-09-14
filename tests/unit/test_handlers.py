import pytest
import logging
from datetime import datetime

from app.infra.events import handlers
from app.services.client_service import NotFoundError


# --- Fixtures utilitaires ---
class DummyCustomer:
    def __init__(self, id=1, orders_count=0, last_order_date=None):
        self.id = id
        self.orders_count = orders_count
        self.last_order_date = last_order_date


class DummyDB:
    def __init__(self):
        self._committed = False
    def commit(self):
        self._committed = True


# ---------------- parse_iso ----------------

def test_parse_iso_none():
    assert handlers._parse_iso(None) is None


def test_parse_iso_invalid():
    assert handlers._parse_iso("not-a-date") is None


def test_parse_iso_valid():
    iso = datetime.now().isoformat()
    dt = handlers._parse_iso(iso)
    assert isinstance(dt, datetime)


# ---------------- handle_order_created ----------------

@pytest.mark.asyncio
async def test_handle_order_created_ok(monkeypatch):
    db = DummyDB()
    cust = DummyCustomer()

    class DummyService:
        def get(self, cid): return cust
    monkeypatch.setattr(handlers, "CustomerService", lambda db, mq=None: DummyService())

    payload = {"customer_id": 1, "created_at": datetime.now().isoformat()}
    await handlers.handle_order_created(payload, db)

    assert db._committed is True


@pytest.mark.asyncio
async def test_handle_order_created_without_date(monkeypatch):
    db = DummyDB()
    cust = DummyCustomer()
    monkeypatch.setattr(handlers, "CustomerService", lambda db, mq=None: type("S", (), {"get": lambda self, cid: cust})())

    payload = {"customer_id": 1}
    await handlers.handle_order_created(payload, db)
    assert db._committed is True


@pytest.mark.asyncio
async def test_handle_order_created_no_customer_id(caplog):
    db = DummyDB()
    caplog.set_level(logging.WARNING)
    await handlers.handle_order_created({"created_at": datetime.now().isoformat()}, db)
    assert "order.created sans customer_id" in caplog.text


@pytest.mark.asyncio
async def test_handle_order_created_not_found(monkeypatch, caplog):
    db = DummyDB()
    monkeypatch.setattr(handlers, "CustomerService", lambda db, mq=None: type("S", (), {"get": lambda self, cid: (_ for _ in ()).throw(NotFoundError())})())

    caplog.set_level(logging.WARNING)
    await handlers.handle_order_created({"customer_id": 99}, db)
    assert "non trouvé" in caplog.text


# ---------------- handle_order_deleted ----------------

@pytest.mark.asyncio
async def test_handle_order_deleted_ok(monkeypatch):
    db = DummyDB()
    cust = DummyCustomer(orders_count=3)
    monkeypatch.setattr(handlers, "CustomerService", lambda db, mq=None: type("S", (), {"get": lambda self, cid: cust})())

    await handlers.handle_order_deleted({"customer_id": 1}, db)
    assert db._committed is True


@pytest.mark.asyncio
async def test_handle_order_deleted_no_customer_id(caplog):
    db = DummyDB()
    caplog.set_level(logging.WARNING)
    await handlers.handle_order_deleted({}, db)
    assert "order.deleted sans customer_id" in caplog.text


@pytest.mark.asyncio
async def test_handle_order_deleted_not_found(monkeypatch, caplog):
    db = DummyDB()
    monkeypatch.setattr(handlers, "CustomerService", lambda db, mq=None: type("S", (), {"get": lambda self, cid: (_ for _ in ()).throw(NotFoundError())})())
    caplog.set_level(logging.WARNING)
    await handlers.handle_order_deleted({"customer_id": 42}, db)
    assert "non trouvé" in caplog.text


@pytest.mark.asyncio
async def test_handle_order_deleted_count_zero(monkeypatch):
    db = DummyDB()
    cust = DummyCustomer(orders_count=0)
    monkeypatch.setattr(handlers, "CustomerService", lambda db, mq=None: type("S", (), {"get": lambda self, cid: cust})())
    await handlers.handle_order_deleted({"customer_id": 1}, db)
    assert db._committed is True


# ---------------- handle_order_confirmed ----------------

@pytest.mark.asyncio
async def test_handle_order_confirmed_ok(monkeypatch):
    db = DummyDB()
    cust = DummyCustomer()
    monkeypatch.setattr(handlers, "CustomerService", lambda db, mq=None: type("S", (), {"get": lambda self, cid: cust})())

    payload = {"customer_id": 1, "created_at": datetime.now().isoformat()}
    await handlers.handle_order_confirmed(payload, db)

    assert cust.orders_count == 1
    assert db._committed is True


@pytest.mark.asyncio
async def test_handle_order_confirmed_no_customer_id(caplog):
    db = DummyDB()
    caplog.set_level(logging.WARNING)
    await handlers.handle_order_confirmed({}, db)
    assert "order.confirmed sans customer_id" in caplog.text


@pytest.mark.asyncio
async def test_handle_order_confirmed_not_found(monkeypatch, caplog):
    db = DummyDB()
    monkeypatch.setattr(handlers, "CustomerService", lambda db, mq=None: type("S", (), {"get": lambda self, cid: (_ for _ in ()).throw(NotFoundError())})())
    caplog.set_level(logging.WARNING)
    await handlers.handle_order_confirmed({"customer_id": 123}, db)
    assert "non trouvé" in caplog.text


# ---------------- handle_order_rejected ----------------

@pytest.mark.asyncio
async def test_handle_order_rejected_ok(caplog):
    db = DummyDB()
    caplog.set_level(logging.INFO)
    await handlers.handle_order_rejected({"customer_id": 99}, db)
    assert "order.rejected reçu" in caplog.text


@pytest.mark.asyncio
async def test_handle_order_rejected_no_id(caplog):
    db = DummyDB()
    caplog.set_level(logging.WARNING)
    await handlers.handle_order_rejected({}, db)
    assert "order.rejected sans customer_id" in caplog.text


# ---------------- handle_order_cancelled ----------------

@pytest.mark.asyncio
async def test_handle_order_cancelled_decrement(monkeypatch):
    db = DummyDB()
    cust = DummyCustomer(orders_count=2)
    monkeypatch.setattr(handlers, "CustomerService", lambda db, mq=None: type("S", (), {"get": lambda self, cid: cust})())
    await handlers.handle_order_cancelled({"customer_id": 1}, db)
    assert cust.orders_count == 1
    assert db._committed is True


@pytest.mark.asyncio
async def test_handle_order_cancelled_no_id(caplog):
    db = DummyDB()
    caplog.set_level(logging.WARNING)
    await handlers.handle_order_cancelled({}, db)
    assert "order.cancelled sans customer_id" in caplog.text


@pytest.mark.asyncio
async def test_handle_order_cancelled_not_found(monkeypatch, caplog):
    db = DummyDB()
    monkeypatch.setattr(handlers, "CustomerService", lambda db, mq=None: type("S", (), {"get": lambda self, cid: (_ for _ in ()).throw(NotFoundError())})())
    caplog.set_level(logging.WARNING)
    await handlers.handle_order_cancelled({"customer_id": 55}, db)
    assert "non trouvé" in caplog.text
