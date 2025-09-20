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
        self._rolled_back = False

    def commit(self):
        self._committed = True

    def rollback(self):
        self._rolled_back = True


class DummyMQ:
    async def publish_message(self, rk, payload):
        self.last = (rk, payload)


class DummyService:
    def __init__(self, customer=None, raise_notfound=False):
        self.customer = customer or DummyCustomer()
        self.raise_notfound = raise_notfound
        self.mq = DummyMQ()

    def get(self, cid):
        if self.raise_notfound:
            raise NotFoundError()
        return self.customer


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
    svc = DummyService()
    monkeypatch.setattr(handlers, "_get_service", lambda db: svc)

    payload = {"order_id": 1, "customer_id": 1, "created_at": datetime.now().isoformat()}
    await handlers.handle_order_created(payload, db)

    assert db._committed is True
    assert svc.mq.last[0] == "order.customer_validated"


@pytest.mark.asyncio
async def test_handle_order_created_without_date(monkeypatch):
    db = DummyDB()
    svc = DummyService()
    monkeypatch.setattr(handlers, "_get_service", lambda db: svc)

    payload = {"order_id": 2, "customer_id": 1}
    await handlers.handle_order_created(payload, db)

    assert db._committed is True
    assert svc.mq.last[0] == "order.customer_validated"


@pytest.mark.asyncio
async def test_handle_order_created_no_customer_id(monkeypatch, caplog):
    db = DummyDB()
    svc = DummyService()
    monkeypatch.setattr(handlers, "_get_service", lambda db: svc)

    caplog.set_level(logging.WARNING)
    payload = {"order_id": 3}
    await handlers.handle_order_created(payload, db)

    assert "sans customer_id" in caplog.text
    assert svc.mq.last[0] == "order.rejected"


@pytest.mark.asyncio
async def test_handle_order_created_not_found(monkeypatch, caplog):
    db = DummyDB()
    svc = DummyService(raise_notfound=True)
    monkeypatch.setattr(handlers, "_get_service", lambda db: svc)

    caplog.set_level(logging.WARNING)
    payload = {"order_id": 4, "customer_id": 99}
    await handlers.handle_order_created(payload, db)

    assert db._rolled_back is True
    assert "introuvable" in caplog.text
    assert svc.mq.last[0] == "order.rejected"


# ---------------- handle_order_confirmed ----------------

@pytest.mark.asyncio
async def test_handle_order_confirmed_ok(monkeypatch):
    db = DummyDB()
    cust = DummyCustomer()
    svc = DummyService(customer=cust)
    monkeypatch.setattr(handlers, "_get_service", lambda db: svc)

    payload = {"order_id": 10, "customer_id": 1, "created_at": datetime.now().isoformat()}
    await handlers.handle_order_confirmed(payload, db)

    assert cust.orders_count == 1
    assert db._committed is True


@pytest.mark.asyncio
async def test_handle_order_confirmed_no_order_id(caplog):
    db = DummyDB()
    caplog.set_level(logging.WARNING)
    await handlers.handle_order_confirmed({}, db)
    assert "payload sans order_id" in caplog.text


@pytest.mark.asyncio
async def test_handle_order_confirmed_no_customer_id(caplog):
    db = DummyDB()
    caplog.set_level(logging.WARNING)
    payload = {"order_id": 11}
    await handlers.handle_order_confirmed(payload, db)
    assert "sans customer_id" in caplog.text


@pytest.mark.asyncio
async def test_handle_order_confirmed_not_found(monkeypatch, caplog):
    db = DummyDB()
    svc = DummyService(raise_notfound=True)
    monkeypatch.setattr(handlers, "_get_service", lambda db: svc)

    caplog.set_level(logging.WARNING)
    payload = {"order_id": 12, "customer_id": 42}
    await handlers.handle_order_confirmed(payload, db)
    assert db._rolled_back is True
    assert "introuvable" in caplog.text


# ---------------- handle_order_rejected ----------------

@pytest.mark.asyncio
async def test_handle_order_rejected_logs(caplog):
    db = DummyDB()
    caplog.set_level(logging.INFO)
    await handlers.handle_order_rejected({"order_id": 50, "reason": "bad", "customer_id": 9}, db)
    assert "[order.rejected]" in caplog.text


# ---------------- handle_order_cancelled ----------------

@pytest.mark.asyncio
async def test_handle_order_cancelled_decrement(monkeypatch):
    db = DummyDB()
    cust = DummyCustomer(orders_count=2)
    svc = DummyService(customer=cust)
    monkeypatch.setattr(handlers, "_get_service", lambda db: svc)

    await handlers.handle_order_cancelled({"order_id": 20, "customer_id": 1}, db)
    assert cust.orders_count == 1
    assert db._committed is True


@pytest.mark.asyncio
async def test_handle_order_cancelled_zero(monkeypatch):
    db = DummyDB()
    cust = DummyCustomer(orders_count=0)
    svc = DummyService(customer=cust)
    monkeypatch.setattr(handlers, "_get_service", lambda db: svc)

    await handlers.handle_order_cancelled({"order_id": 21, "customer_id": 1}, db)
    assert cust.orders_count == 0  # pas de décrément


@pytest.mark.asyncio
async def test_handle_order_cancelled_no_customer_id(caplog):
    db = DummyDB()
    caplog.set_level(logging.WARNING)
    await handlers.handle_order_cancelled({"order_id": 22}, db)
    assert "order.cancelled" in caplog.text


@pytest.mark.asyncio
async def test_handle_order_cancelled_not_found(monkeypatch, caplog):
    db = DummyDB()
    svc = DummyService(raise_notfound=True)
    monkeypatch.setattr(handlers, "_get_service", lambda db: svc)

    caplog.set_level(logging.WARNING)
    await handlers.handle_order_cancelled({"order_id": 23, "customer_id": 55}, db)
    assert db._rolled_back is True
    assert "introuvable" in caplog.text


# ---------------- handle_order_deleted ----------------

@pytest.mark.asyncio
async def test_handle_order_deleted_ok(monkeypatch):
    db = DummyDB()
    cust = DummyCustomer(orders_count=3)
    svc = DummyService(customer=cust)
    monkeypatch.setattr(handlers, "_get_service", lambda db: svc)

    await handlers.handle_order_deleted({"order_id": 30, "customer_id": 1}, db)
    assert cust.orders_count == 2
    assert db._committed is True


@pytest.mark.asyncio
async def test_handle_order_deleted_no_customer_id(caplog):
    db = DummyDB()
    caplog.set_level(logging.WARNING)
    await handlers.handle_order_deleted({"order_id": 31}, db)
    assert "order.deleted" in caplog.text


@pytest.mark.asyncio
async def test_handle_order_deleted_not_found(monkeypatch, caplog):
    db = DummyDB()
    svc = DummyService(raise_notfound=True)
    monkeypatch.setattr(handlers, "_get_service", lambda db: svc)

    caplog.set_level(logging.WARNING)
    await handlers.handle_order_deleted({"order_id": 32, "customer_id": 42}, db)
    assert db._rolled_back is True
    assert "introuvable" in caplog.text


@pytest.mark.asyncio
async def test_handle_order_deleted_zero(monkeypatch):
    db = DummyDB()
    cust = DummyCustomer(orders_count=0)
    svc = DummyService(customer=cust)
    monkeypatch.setattr(handlers, "_get_service", lambda db: svc)

    await handlers.handle_order_deleted({"order_id": 33, "customer_id": 1}, db)
    assert cust.orders_count == 0
    assert db._committed is True


@pytest.mark.asyncio
async def test_handle_customer_validate_request_ok(monkeypatch):
    db = DummyDB()
    svc = DummyService()
    monkeypatch.setattr(handlers, "_get_service", lambda db: svc)

    payload = {"order_id": 1, "customer_id": 123}
    await handlers.handle_customer_validate_request(payload, db)

    assert svc.mq.last[0] == "order.customer_validated"


@pytest.mark.asyncio
async def test_handle_customer_validate_request_no_customer_id(monkeypatch, caplog):
    db = DummyDB()
    svc = DummyService()
    monkeypatch.setattr(handlers, "_get_service", lambda db: svc)

    caplog.set_level(logging.WARNING)
    payload = {"order_id": 2}
    await handlers.handle_customer_validate_request(payload, db)

    assert "sans customer_id" in caplog.text
    assert svc.mq.last[0] == "order.rejected"


@pytest.mark.asyncio
async def test_handle_customer_validate_request_not_found(monkeypatch, caplog):
    db = DummyDB()
    svc = DummyService(raise_notfound=True)
    monkeypatch.setattr(handlers, "_get_service", lambda db: svc)

    caplog.set_level(logging.WARNING)
    payload = {"order_id": 3, "customer_id": 999}
    await handlers.handle_customer_validate_request(payload, db)

    assert "introuvable" in caplog.text
    assert svc.mq.last[0] == "order.rejected"

@pytest.mark.asyncio
async def test_handle_order_rejected_no_reason(monkeypatch, caplog):
    db = DummyDB()
    caplog.set_level(logging.INFO)
    payload = {"order_id": 100}
    await handlers.handle_order_rejected(payload, db)
    assert "Unknown" in caplog.text
