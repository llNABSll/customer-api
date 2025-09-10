import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from pydantic import ValidationError

from app.schemas.client import (
    ClientCreate, ClientUpdate, ClientResponse
)

# ----- ClientCreate -----

def test_client_create_valid():
    c = ClientCreate(
        name="Test User",
        email="test@example.com",
        company="Test Inc",
        phone="1234567890"
    )
    assert c.name == "Test User"
    assert c.email == "test@example.com"
    assert c.company == "Test Inc"
    assert c.phone == "1234567890"

@pytest.mark.parametrize("field,value", [
    ("name", ""),  # vide
    ("email", "not-an-email"),  # email invalide
    ("phone", "123"),  # trop court
])
def test_client_create_invalid(field, value):
    data = {"name": "Valid Name", "email": "valid@email.com", "phone": "12345"}
    data[field] = value
    with pytest.raises(ValidationError):
        ClientCreate(**data)

def test_client_create_too_long_fields():
    long_name = "a" * 256
    long_company = "b" * 256
    long_phone = "1" * 33
    with pytest.raises(ValidationError):
        ClientCreate(name=long_name, email="ok@test.com")
    with pytest.raises(ValidationError):
        ClientCreate(name="ok", email="ok@test.com", company=long_company)
    with pytest.raises(ValidationError):
        ClientCreate(name="ok", email="ok@test.com", phone=long_phone)


# ----- ClientUpdate -----

def test_client_update_empty_ok():
    u = ClientUpdate()
    assert u.model_dump(exclude_unset=True) == {}

def test_client_update_valid():
    u = ClientUpdate(name="New Name", phone="0987654321")
    assert u.name == "New Name"
    assert u.phone == "0987654321"

def test_client_update_all_fields():
    u = ClientUpdate(
        name="Full",
        email="full@test.com",
        company="FullCorp",
        phone="55555"
    )
    d = u.model_dump(exclude_unset=True)
    assert d["name"] == "Full"
    assert d["email"] == "full@test.com"
    assert d["company"] == "FullCorp"
    assert d["phone"] == "55555"

@pytest.mark.parametrize("field,value", [
    ("email", "bad-email"),
    ("name", ""),
    ("phone", "123"),   # trop court
    ("phone", "9" * 40),  # trop long
])
def test_client_update_invalid(field, value):
    with pytest.raises(ValidationError):
        ClientUpdate(**{field: value})


# ----- ClientResponse -----

def test_client_response_from_orm():
    fake_orm_client = MagicMock()
    fake_orm_client.id = 1
    fake_orm_client.name = "Orm User"
    fake_orm_client.email = "orm@example.com"
    fake_orm_client.company = "Orm Inc"
    fake_orm_client.phone = "111222333"
    fake_orm_client.version = 5
    fake_orm_client.created_at = datetime.now(timezone.utc)
    fake_orm_client.updated_at = datetime.now(timezone.utc)

    resp = ClientResponse.model_validate(fake_orm_client)
    assert resp.id == 1
    assert resp.name == "Orm User"
    assert resp.email == "orm@example.com"
    assert resp.version == 5

def test_client_response_missing_fields():
    """Manque un champ obligatoire → ValidationError"""
    with pytest.raises(ValidationError):
        ClientResponse(
            id=1,
            name="X",
            email="x@test.com",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            # version manquant
        )
