import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone
from pydantic import ValidationError

from app.schemas.client import ClientCreate, ClientUpdate, ClientResponse


# ----- ClientCreate -----

def test_client_create_valid():
    c = ClientCreate(
        first_name="Test",
        last_name="User",
        email="test@example.com",
        company="Test Inc",
        phone="1234567890"
    )
    assert c.first_name == "Test"
    assert c.last_name == "User"
    assert c.email == "test@example.com"


@pytest.mark.parametrize("field,value", [
    ("first_name", ""),  # vide
    ("email", "not-an-email"),  # email invalide
    ("phone", "123"),  # trop court
])
def test_client_create_invalid(field, value):
    data = {"first_name": "Valid", "last_name": "Name", "email": "valid@email.com", "phone": "12345"}
    data[field] = value
    with pytest.raises(ValidationError):
        ClientCreate(**data)


# ----- ClientUpdate -----

def test_client_update_empty_ok():
    u = ClientUpdate()
    assert u.model_dump(exclude_unset=True) == {}


def test_client_update_valid():
    u = ClientUpdate(first_name="New", phone="0987654321")
    assert u.first_name == "New"
    assert u.phone == "0987654321"


# ----- ClientResponse -----

def test_client_response_from_orm():
    fake = MagicMock()
    fake.id = 1
    fake.first_name = "Orm"
    fake.last_name = "User"
    fake.email = "orm@example.com"
    fake.company = "Orm Inc"
    fake.phone = "111222333"
    fake.version = 5
    fake.created_at = datetime.now(timezone.utc)
    fake.updated_at = datetime.now(timezone.utc)
    # Ajout des champs adresse obligatoires
    fake.address_line1 = "1 rue de test"
    fake.address_line2 = ""
    fake.postal_code = "75000"
    fake.city = "Paris"
    fake.state = "IDF"
    fake.country_code = "FR"

    resp = ClientResponse.model_validate(fake)
    assert resp.id == 1
    assert resp.first_name == "Orm"
    assert resp.last_name == "User"
    assert resp.email == "orm@example.com"


def test_client_response_missing_fields():
    with pytest.raises(ValidationError):
        ClientResponse(
            id=1,
            first_name="X",
            last_name="Y",
            email="x@test.com",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            # version manquant
        )
