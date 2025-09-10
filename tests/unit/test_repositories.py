# tests/unit/test_repositories.py
import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.repositories import client as repo
from app.schemas.client import ClientCreate, ClientUpdate


def test_create_and_get_and_delete(session):
    data = ClientCreate(name="Test Client", email="test@client.com")
    c = repo.create_client(session, data)
    assert c.id is not None

    found = repo.get_client(session, c.id)
    assert found.email == "test@client.com"

    deleted = repo.delete_client(session, c.id)
    assert deleted.id == c.id

    assert repo.get_client(session, c.id) is None


def test_list_clients(session):
    repo.create_client(session, ClientCreate(name="C1", email="c1@test.com"))
    repo.create_client(session, ClientCreate(name="C2", email="c2@test.com"))

    clients = repo.get_clients(session, skip=0, limit=10)
    assert len(clients) == 2
    assert clients[0].name == "C1"

    # Pagination : skip=1 → on saute le premier
    paginated = repo.get_clients(session, skip=1, limit=10)
    assert len(paginated) == 1
    assert paginated[0].name == "C2"


def test_update_client_ok(session):
    c = repo.create_client(session, ClientCreate(name="Old Name", email="update@test.com"))
    updated = repo.update_client(session, c.id, ClientUpdate(name="New Name"))
    assert updated.name == "New Name"
    assert updated.version == 2  # Check version increment


def test_update_client_partial(session):
    c = repo.create_client(session, ClientCreate(name="Partial", email="partial@test.com"))
    old_version = c.version
    updated = repo.update_client(session, c.id, ClientUpdate())
    assert updated.name == "Partial"
    assert updated.version == old_version


def test_update_client_not_found(session):
    result = repo.update_client(session, 9999, ClientUpdate(name="X"))
    assert result is None


def test_create_client_integrity_error(session):
    repo.create_client(session, ClientCreate(name="Dup", email="dup@test.com"))
    with pytest.raises(IntegrityError):
        repo.create_client(session, ClientCreate(name="Dup", email="dup@test.com"))


def test_delete_client_not_found(session):
    assert repo.delete_client(session, 9999) is None


def test_create_client_sqlalchemy_error(monkeypatch, session):
    """Simule une SQLAlchemyError pour vérifier rollback et logging."""
    monkeypatch.setattr(session, "commit", lambda: (_ for _ in ()).throw(SQLAlchemyError("boom")))
    with pytest.raises(SQLAlchemyError):
        repo.create_client(session, ClientCreate(name="Err", email="err@test.com"))


def test_update_client_sqlalchemy_error(monkeypatch, session):
    c = repo.create_client(session, ClientCreate(name="U1", email="u1@test.com"))

    def bad_commit():
        raise SQLAlchemyError("fail")

    monkeypatch.setattr(session, "commit", bad_commit)

    with pytest.raises(SQLAlchemyError):
        repo.update_client(session, c.id, ClientUpdate(name="oops"))


def test_delete_client_sqlalchemy_error(monkeypatch, session):
    c = repo.create_client(session, ClientCreate(name="D1", email="d1@test.com"))

    def bad_commit():
        raise SQLAlchemyError("fail")

    monkeypatch.setattr(session, "commit", bad_commit)

    with pytest.raises(SQLAlchemyError):
        repo.delete_client(session, c.id)
