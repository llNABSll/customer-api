# tests/test_schemas.py
from __future__ import annotations
import pytest
from app.schemas.client import ClientCreate, ClientUpdate, ClientOut

def test_client_create_valid():
    c = ClientCreate(email="test@example.com", name="Test")
    assert c.email == "test@example.com"

def test_client_create_invalid_email():
    with pytest.raises(Exception):
        ClientCreate(email="not-an-email")

def test_client_update_partial():
    u = ClientUpdate(name="New Name", email="user@example.com")
    assert u.name == "New Name"
    assert u.email == "user@example.com"

def test_client_out_shape():
    o = ClientOut(id=1, email="a@b.c", name="X")
    assert o.id == 1
    assert o.email == "a@b.c"
