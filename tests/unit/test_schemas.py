# tests/unit/test_schemas.py
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

@pytest.mark.parametrize("field,value", [
    ("name", ""),
    ("email", "not-an-email"),
    ("phone", "123"), # too short
])
def test_client_create_invalid(field, value):
    data = {"name": "Valid Name", "email": "valid@email.com"}
    data[field] = value
    with pytest.raises(ValidationError):
        ClientCreate(**data)

# ----- ClientUpdate -----
def test_client_update_empty_ok():
    u = ClientUpdate()
    assert u.model_dump(exclude_unset=True) == {}

def test_client_update_valid():
    u = ClientUpdate(name="New Name", phone="0987654321")
    assert u.name == "New Name"
    assert u.phone == "0987654321"

@pytest.mark.parametrize("field,value", [
    ("email", "bad-email"),
    ("name", ""),
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
    fake_orm_client.created_at = datetime.now(timezone.utc)
    fake_orm_client.updated_at = datetime.now(timezone.utc)

    resp = ClientResponse.model_validate(fake_orm_client)
    assert resp.id == 1
    assert resp.name == "Orm User"
    assert resp.email == "orm@example.com"
