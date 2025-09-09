# tests/unit/test_services.py
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
    fake_mq.publish_message.assert_awaited_with("customer.created", {"id": 1, "name": "New", "email": "new@test.com"})

@pytest.mark.asyncio
async def test_create_email_conflict(fake_db, fake_mq, monkeypatch):
    patch_repo(
        monkeypatch,
        create_client=lambda db, data: (_ for _ in ()).throw(IntegrityError("m", "p", "o"))
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
