import pytest
from unittest.mock import MagicMock, AsyncMock
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from app.services.client_service import (
    CustomerService,
    NotFoundError,
    EmailAlreadyExistsError,
    ConcurrencyConflictError,
)
from app.models.client import Client
from app.schemas.client import ClientCreate, ClientUpdate


# ---------- Fixtures ----------
@pytest.fixture
def fake_db():
    return MagicMock()

@pytest.fixture
def fake_mq():
    mq = MagicMock()
    mq.publish_message = AsyncMock(return_value=None)
    return mq

@pytest.fixture
def client_instance():
    return Client(
        id=1, name="Test Client", email="test@example.com", version=1
    )

# Helper pour patcher le repo
def patch_repo(monkeypatch, **methods):
    import app.repositories.client as repo
    for name, impl in methods.items():
        monkeypatch.setattr(repo, name, impl)


# ---------- GET ----------
def test_get_found(fake_db, fake_mq, client_instance, monkeypatch):
    patch_repo(monkeypatch, get_client=lambda db, cid: client_instance)
    svc = CustomerService(fake_db, fake_mq)
    assert svc.get(1) == client_instance

def test_get_not_found(fake_db, fake_mq, monkeypatch):
    patch_repo(monkeypatch, get_client=lambda db, cid: None)
    svc = CustomerService(fake_db, fake_mq)
    with pytest.raises(NotFoundError):
        svc.get(123)


# ---------- GET BY EMAIL ----------
def test_get_by_email_found(fake_db, fake_mq):
    fake_client = Client(id=2, name="Email", email="x@test.com")
    fake_db.query().filter().first.return_value = fake_client
    svc = CustomerService(fake_db, fake_mq)
    result = svc.get_by_email("x@test.com")
    assert result == fake_client

def test_get_by_email_not_found(fake_db, fake_mq):
    fake_db.query().filter().first.return_value = None
    svc = CustomerService(fake_db, fake_mq)
    result = svc.get_by_email("nope@test.com")
    assert result is None


# ---------- LIST ----------
def test_list_no_filters(fake_db, fake_mq):
    fake_clients = [Client(id=1, name="C1", email="c1@test.com")]

    fake_query = MagicMock()
    fake_query.order_by.return_value = fake_query
    fake_query.offset.return_value = fake_query
    fake_query.limit.return_value = fake_query
    fake_query.all.return_value = fake_clients

    fake_db.query.return_value = fake_query

    svc = CustomerService(fake_db, fake_mq)
    result = svc.list()

    assert result == fake_clients
    fake_db.query.assert_called_once_with(Client)
    fake_query.order_by.assert_called_once() 
    fake_query.offset.assert_called_once_with(0)
    fake_query.limit.assert_called_once_with(10)

def test_list_with_filters(fake_db, fake_mq):
    # Simule que query renvoie un Query-like chainable
    fake_query = MagicMock()
    fake_query.filter.return_value = fake_query
    fake_query.order_by.return_value = fake_query
    fake_query.offset.return_value = fake_query
    fake_query.limit.return_value = fake_query
    fake_query.all.return_value = [Client(id=1, name="Filtered", email="f@test.com")]

    fake_db.query.return_value = fake_query
    svc = CustomerService(fake_db, fake_mq)
    result = svc.list(q="f", company="TestCo", sort_by="name", sort_dir="desc")
    assert result[0].name == "Filtered"
    assert fake_query.filter.called
    assert fake_query.order_by.called


# ---------- CREATE ----------
@pytest.mark.asyncio
async def test_create_ok(fake_db, fake_mq, monkeypatch):
    patch_repo(
        monkeypatch,
        create_client=lambda db, data: Client(id=1, **data.model_dump()),
    )
    svc = CustomerService(fake_db, fake_mq)
    created = await svc.create(ClientCreate(name="New", email="new@test.com"))
    assert created.id == 1
    fake_mq.publish_message.assert_awaited_with(
        "customer.created", {"id": 1, "name": "New", "email": "new@test.com"}
    )

@pytest.mark.asyncio
async def test_create_email_conflict(fake_db, fake_mq, monkeypatch):
    patch_repo(
        monkeypatch,
        create_client=lambda db, data: (_ for _ in ()).throw(IntegrityError("m", "p", "o")),
    )
    svc = CustomerService(fake_db, fake_mq)
    with pytest.raises(EmailAlreadyExistsError):
        await svc.create(ClientCreate(name="Dup", email="dup@test.com"))


# ---------- UPDATE ----------
@pytest.mark.asyncio
async def test_update_ok(fake_db, fake_mq, client_instance, monkeypatch):
    patch_repo(
        monkeypatch,
        get_client=lambda db, cid: client_instance,
        update_client=lambda db, cid, data: Client(id=1, name=data.name, email=client_instance.email),
    )
    svc = CustomerService(fake_db, fake_mq)
    updated = await svc.update(1, ClientUpdate(name="Updated Name"))
    assert updated.name == "Updated Name"
    fake_mq.publish_message.assert_awaited()

@pytest.mark.asyncio
async def test_update_not_found(fake_db, fake_mq, monkeypatch):
    patch_repo(monkeypatch, get_client=lambda db, cid: None)
    svc = CustomerService(fake_db, fake_mq)
    with pytest.raises(NotFoundError):
        await svc.update(1, ClientUpdate(name="X"))

@pytest.mark.asyncio
async def test_update_version_conflict(fake_db, fake_mq, client_instance, monkeypatch):
    client_instance.version = 2
    patch_repo(monkeypatch, get_client=lambda db, cid: client_instance)
    svc = CustomerService(fake_db, fake_mq)
    with pytest.raises(ConcurrencyConflictError):
        await svc.update(1, ClientUpdate(name="X"), expected_version=1)

@pytest.mark.asyncio
async def test_update_integrity_error(fake_db, fake_mq, client_instance, monkeypatch):
    def bad_update(db, cid, data):
        raise IntegrityError("msg", "params", "orig")

    patch_repo(monkeypatch, get_client=lambda db, cid: client_instance, update_client=bad_update)
    svc = CustomerService(fake_db, fake_mq)
    with pytest.raises(EmailAlreadyExistsError):
        await svc.update(1, ClientUpdate(name="Dup"))

@pytest.mark.asyncio
async def test_update_stale_data_error(fake_db, fake_mq, client_instance, monkeypatch):
    def bad_update(db, cid, data):
        raise StaleDataError("msg")

    patch_repo(monkeypatch, get_client=lambda db, cid: client_instance, update_client=bad_update)
    svc = CustomerService(fake_db, fake_mq)
    with pytest.raises(ConcurrencyConflictError):
        await svc.update(1, ClientUpdate(name="Stale"))


# ---------- DELETE ----------
@pytest.mark.asyncio
async def test_delete_ok(fake_db, fake_mq, client_instance, monkeypatch):
    patch_repo(monkeypatch, delete_client=lambda db, cid: client_instance)
    svc = CustomerService(fake_db, fake_mq)
    deleted = await svc.delete(1)
    assert deleted == client_instance
    fake_mq.publish_message.assert_awaited_with("customer.deleted", {"id": 1})

@pytest.mark.asyncio
async def test_delete_not_found(fake_db, fake_mq, monkeypatch):
    patch_repo(monkeypatch, delete_client=lambda db, cid: None)
    svc = CustomerService(fake_db, fake_mq)
    with pytest.raises(NotFoundError):
        await svc.delete(1)
