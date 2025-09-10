# tests/unit/test_security.py
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.security import security


# ----- _roles_from_claims -----

def test_roles_from_claims_realm_and_resource():
    payload = {
        "realm_access": {"roles": ["realm:admin"]},
        "resource_access": {
            "product-api": {"roles": ["product:read"]},
            "other": {"roles": ["user"]}
        },
        "roles": ["custom:role"]
    }
    roles = security._roles_from_claims(payload)
    assert {"realm:admin", "product:read", "user", "custom:role"} <= roles


def test_roles_from_claims_empty():
    assert security._roles_from_claims({}) == set()


# ----- _Verifier -----

def test_verifier_init_missing_settings():
    with pytest.raises(RuntimeError):
        security._Verifier("", "")


def test_get_verifier_creates_instance(monkeypatch):
    monkeypatch.setattr(security, "_verifier", None)
    monkeypatch.setattr(security, "_JWKS_URL", "http://fake/jwks")
    monkeypatch.setattr(security, "_ISSUER", "http://issuer")

    class DummyVerifier:
        def __init__(self, url, iss):
            self.url, self.iss = url, iss
    monkeypatch.setattr(security, "_Verifier", DummyVerifier)

    v = security._get_verifier()
    assert isinstance(v, DummyVerifier)
    assert v.url == "http://fake/jwks"


# ----- AuthContext -----

def test_authcontext_fields():
    ctx = security.AuthContext("bob", "bob@example.com", ["x"])
    assert ctx.user == "bob"
    assert ctx.email == "bob@example.com"
    assert "x" in ctx.roles


# ----- require_user (gateway mode) -----

def test_require_user_gateway_mode():
    ctx = security.require_user(
        x_auth_request_user="bob",
        x_auth_request_email="bob@example.com",
        x_auth_request_groups="product:read,product:write"
    )
    assert ctx.user == "bob"
    assert ctx.email == "bob@example.com"
    assert {"product:read", "product:write"} <= set(ctx.roles)


def test_require_user_gateway_groups_empty():
    ctx = security.require_user(
        x_auth_request_user="bob",
        x_auth_request_groups=""
    )
    assert ctx.user == "bob"
    assert ctx.roles == []


def test_require_user_gateway_groups_invalid_type():
    ctx = security.require_user(
        x_auth_request_user="bob",
        x_auth_request_groups=123  # mauvais type → ignoré
    )
    assert ctx.roles == []


def test_require_user_gateway_user_invalid_type():
    with pytest.raises(HTTPException) as e:
        security.require_user(
            x_auth_request_user=123,
            x_auth_request_groups="product:read"
        )
    assert e.value.status_code == 401
    assert "Unauthorized" in e.value.detail


# ----- require_user (JWT mode) -----

def test_require_user_jwt_valid_with_username(monkeypatch):
    class FakeVerifier:
        def decode(self, token):
            return {
                "preferred_username": "alice",
                "email": "alice@example.com",
                "realm_access": {"roles": ["product:read"]}
            }

    monkeypatch.setattr(security, "_get_verifier", lambda: FakeVerifier())
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="faketoken")

    ctx = security.require_user(creds=creds)
    assert ctx.user == "alice"
    assert ctx.email == "alice@example.com"
    assert "product:read" in ctx.roles


def test_require_user_jwt_valid_with_sub(monkeypatch):
    class FakeVerifier:
        def decode(self, token):
            return {"sub": "user123", "roles": []}

    monkeypatch.setattr(security, "_get_verifier", lambda: FakeVerifier())
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="tok")

    ctx = security.require_user(creds=creds)
    assert ctx.user == "user123"
    assert ctx.email is None


def test_require_user_jwt_valid_unknown(monkeypatch):
    class FakeVerifier:
        def decode(self, token):
            return {}

    monkeypatch.setattr(security, "_get_verifier", lambda: FakeVerifier())
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="tok")

    ctx = security.require_user(creds=creds)
    assert ctx.user == "unknown"


def test_require_user_jwt_invalid(monkeypatch, caplog):
    class FakeVerifier:
        def decode(self, token):
            raise Exception("bad token")

    monkeypatch.setattr(security, "_get_verifier", lambda: FakeVerifier())
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="badtoken")

    caplog.set_level("WARNING")
    with pytest.raises(HTTPException) as e:
        security.require_user(creds=creds)
    assert e.value.status_code == 401
    assert "JWT invalide" in caplog.text


def test_require_user_jwt_wrong_scheme():
    creds = HTTPAuthorizationCredentials(scheme="Basic", credentials="tok")
    with pytest.raises(HTTPException):
        security.require_user(creds=creds)


# ----- require_user (no credentials) -----

def test_require_user_no_credentials():
    with pytest.raises(HTTPException) as e:
        security.require_user()
    assert e.value.status_code == 401


# ----- require_read / require_write -----

def test_require_read_ok():
    ctx = security.AuthContext("u", None, [security._ROLE_READ])
    assert security.require_read(ctx) is ctx


def test_require_read_forbidden():
    ctx = security.AuthContext("u", None, [])
    with pytest.raises(HTTPException) as e:
        security.require_read(ctx)
    assert e.value.status_code == 403
    assert security._ROLE_READ in e.value.detail


def test_require_write_ok():
    ctx = security.AuthContext("u", None, [security._ROLE_WRITE])
    assert security.require_write(ctx) is ctx


def test_require_write_forbidden():
    ctx = security.AuthContext("u", None, [])
    with pytest.raises(HTTPException) as e:
        security.require_write(ctx)
    assert e.value.status_code == 403
    assert security._ROLE_WRITE in e.value.detail
