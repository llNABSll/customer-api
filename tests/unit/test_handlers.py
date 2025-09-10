# tests/unit/test_handlers.py
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


@pytest.mark.asyncio
async def test_handle_order_created_ok(monkeypatch):
    db = DummyDB()
    cust = DummyCustomer()

    class DummyService:
        def get(self, cid): return cust

    monkeypatch.setattr(handlers, "CustomerService", lambda db, mq=None: DummyService())

    payload = {"customer_id": 1, "created_at": datetime.now().isoformat()}
    await handlers.handle_order_created(payload, db)

    assert cust.orders_count == 1
    assert isinstance(cust.last_order_date, datetime)
    assert db._committed is True


@pytest.mark.asyncio
async def test_handle_order_created_without_date(monkeypatch):
    db = DummyDB()
    cust = DummyCustomer()

    class DummyService:
        def get(self, cid): return cust

    monkeypatch.setattr(handlers, "CustomerService", lambda db, mq=None: DummyService())

    payload = {"customer_id": 1}
    await handlers.handle_order_created(payload, db)

    assert cust.orders_count == 1
    # Pas de date modifiée
    assert cust.last_order_date is None


@pytest.mark.asyncio
async def test_handle_order_created_no_customer_id(caplog):
    db = DummyDB()
    caplog.set_level(logging.WARNING)

    payload = {"created_at": datetime.now().isoformat()}
    await handlers.handle_order_created(payload, db)

    assert "order.created sans customer_id" in caplog.text


@pytest.mark.asyncio
async def test_handle_order_created_not_found(monkeypatch, caplog):
    db = DummyDB()

    class DummyService:
        def get(self, cid): raise NotFoundError()

    monkeypatch.setattr(handlers, "CustomerService", lambda db, mq=None: DummyService())

    caplog.set_level(logging.WARNING)
    await handlers.handle_order_created({"customer_id": 99}, db)

    assert "non trouvé" in caplog.text


# ---------------- handle_order_deleted ----------------

@pytest.mark.asyncio
async def test_handle_order_deleted_ok(monkeypatch):
    db = DummyDB()
    cust = DummyCustomer(orders_count=3)

    class DummyService:
        def get(self, cid): return cust

    monkeypatch.setattr(handlers, "CustomerService", lambda db, mq=None: DummyService())

    payload = {"customer_id": 1}
    await handlers.handle_order_deleted(payload, db)

    assert cust.orders_count == 2
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

    class DummyService:
        def get(self, cid): raise NotFoundError()

    monkeypatch.setattr(handlers, "CustomerService", lambda db, mq=None: DummyService())

    caplog.set_level(logging.WARNING)
    await handlers.handle_order_deleted({"customer_id": 42}, db)

    assert "non trouvé" in caplog.text


@pytest.mark.asyncio
async def test_handle_order_deleted_count_zero(monkeypatch):
    db = DummyDB()
    cust = DummyCustomer(orders_count=0)

    class DummyService:
        def get(self, cid): return cust

    monkeypatch.setattr(handlers, "CustomerService", lambda db, mq=None: DummyService())

    payload = {"customer_id": 1}
    await handlers.handle_order_deleted(payload, db)

    # Count reste à 0
    assert cust.orders_count == 0
    assert db._committed is True
