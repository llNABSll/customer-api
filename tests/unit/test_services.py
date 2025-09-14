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
        id=1, first_name="Test", last_name="Client",
        email="test@example.com", company="X", version=1
    )


def patch_repo(monkeypatch, **methods):
    import app.repositories.client as repo
    for name, impl in methods.items():
        monkeypatch.setattr(repo, name, impl)


# ---------------- GET ----------------

def test_get_found(fake_db, fake_mq, client_instance, monkeypatch):
    patch_repo(monkeypatch, get_client=lambda db, cid: client_instance)
    svc = CustomerService(fake_db, fake_mq)
    assert svc.get(1) == client_instance


def test_get_not_found(fake_db, fake_mq, monkeypatch):
    patch_repo(monkeypatch, get_client=lambda db, cid: None)
    svc = CustomerService(fake_db, fake_mq)
    with pytest.raises(NotFoundError):
        svc.get(123)


def test_get_by_email_found(fake_db, fake_mq, client_instance):
    fake_db.query().filter().first.return_value = client_instance
    svc = CustomerService(fake_db, fake_mq)
    c = svc.get_by_email("test@example.com")
    assert c == client_instance


def test_get_by_email_not_found(fake_db, fake_mq):
    fake_db.query().filter().first.return_value = None
    svc = CustomerService(fake_db, fake_mq)
    c = svc.get_by_email("x@y.com")
    assert c is None


# ---------------- LIST ----------------

def test_list_with_filters_and_sort(fake_db, fake_mq, client_instance):
    fake_query = MagicMock()
    fake_query.filter.return_value = fake_query
    fake_query.order_by.return_value = fake_query
    fake_query.offset.return_value = fake_query
    fake_query.limit.return_value.all.return_value = [client_instance]
    fake_db.query.return_value = fake_query

    svc = CustomerService(fake_db, fake_mq)
    results = svc.list(q="Test", company="X", sort_by="email", sort_dir="desc")
    assert results == [client_instance]
    fake_query.filter.assert_called()
    fake_query.order_by.assert_called()


# ---------------- CREATE ----------------

@pytest.mark.asyncio
async def test_create_ok(fake_db, fake_mq, monkeypatch):
    patch_repo(monkeypatch, create_client=lambda db, data: Client(id=1, **data.model_dump()))
    svc = CustomerService(fake_db, fake_mq)
    created = await svc.create(ClientCreate(first_name="New", last_name="User", email="new@test.com"))
    assert created.id == 1
    fake_mq.publish_message.assert_awaited()


@pytest.mark.asyncio
async def test_create_conflict(fake_db, fake_mq, monkeypatch):
    patch_repo(monkeypatch, create_client=lambda db, data: (_ for _ in ()).throw(IntegrityError("x", "y", "z")))
    svc = CustomerService(fake_db, fake_mq)
    with pytest.raises(EmailAlreadyExistsError):
        await svc.create(ClientCreate(first_name="Dup", last_name="User", email="dup@test.com"))


# ---------------- UPDATE ----------------

@pytest.mark.asyncio
async def test_update_not_found(fake_db, fake_mq, monkeypatch):
    patch_repo(monkeypatch, get_client=lambda db, cid: None)
    svc = CustomerService(fake_db, fake_mq)
    with pytest.raises(NotFoundError):
        await svc.update(99, ClientUpdate(first_name="X"))


@pytest.mark.asyncio
async def test_update_version_mismatch(fake_db, fake_mq, client_instance, monkeypatch):
    client_instance.version = 2
    patch_repo(monkeypatch, get_client=lambda db, cid: client_instance)
    svc = CustomerService(fake_db, fake_mq)
    with pytest.raises(ConcurrencyConflictError):
        await svc.update(1, ClientUpdate(first_name="X"), expected_version=1)


@pytest.mark.asyncio
async def test_update_conflict_email(fake_db, fake_mq, client_instance, monkeypatch):
    patch_repo(
        monkeypatch,
        get_client=lambda db, cid: client_instance,
        update_client=lambda db, cid, data: (_ for _ in ()).throw(IntegrityError("x", "y", "z")),
    )
    svc = CustomerService(fake_db, fake_mq)
    with pytest.raises(EmailAlreadyExistsError):
        await svc.update(1, ClientUpdate(first_name="X"))


@pytest.mark.asyncio
async def test_update_conflict_stale(fake_db, fake_mq, client_instance, monkeypatch):
    patch_repo(
        monkeypatch,
        get_client=lambda db, cid: client_instance,
        update_client=lambda db, cid, data: (_ for _ in ()).throw(StaleDataError()),
    )
    svc = CustomerService(fake_db, fake_mq)
    with pytest.raises(ConcurrencyConflictError):
        await svc.update(1, ClientUpdate(first_name="X"))


@pytest.mark.asyncio
async def test_update_ok(fake_db, fake_mq, client_instance, monkeypatch):
    patch_repo(
        monkeypatch,
        get_client=lambda db, cid: client_instance,
        update_client=lambda db, cid, data: client_instance,
    )
    svc = CustomerService(fake_db, fake_mq)
    updated = await svc.update(1, ClientUpdate(first_name="Updated"))
    assert updated == client_instance
    fake_mq.publish_message.assert_awaited()


# ---------------- DELETE ----------------

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
        await svc.delete(42)
