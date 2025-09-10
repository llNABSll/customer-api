from __future__ import annotations
from typing import Optional, Set, List
import logging

from fastapi import Header, HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

import jwt
from jwt import PyJWKClient
from app.core.config import settings

logger = logging.getLogger(__name__)
_http_bearer = HTTPBearer(auto_error=False)

# Rôles (via settings)
_ROLE_READ  = getattr(settings, "ROLE_READ",  "customer:read")
_ROLE_WRITE = getattr(settings, "ROLE_WRITE", "customer:write")

_ISSUER   = getattr(settings, "KEYCLOAK_ISSUER", "")
_JWKS_URL = getattr(settings, "KEYCLOAK_JWKS_URL", "")

class _Verifier:
    def __init__(self, jwks_url: str, issuer: str):
        if not jwks_url or not issuer:
            raise RuntimeError("KEYCLOAK_JWKS_URL / KEYCLOAK_ISSUER non configurés")
        self._jwk = PyJWKClient(jwks_url)
        self._iss = issuer

    def decode(self, token: str) -> dict:
        key = self._jwk.get_signing_key_from_jwt(token).key
        return jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=self._iss,
            audience="customer-api",
            options={"verify_aud": True},
            leeway=10,  # tolérance d'horloge
        )

_verifier: Optional[_Verifier] = None
def _get_verifier() -> _Verifier:
    global _verifier
    if _verifier is None:
        _verifier = _Verifier(_JWKS_URL, _ISSUER)
    return _verifier

def _roles_from_claims(payload: dict) -> Set[str]:
    roles: Set[str] = set()
    # 1) roles realm
    roles |= set(payload.get("realm_access", {}).get("roles", []) or [])
    # 2) roles client (agrège tous les clients)
    res = payload.get("resource_access", {}) or {}
    for _client, data in res.items():
        roles |= set((data or {}).get("roles", []) or [])
    # 3) roles top-level
    roles |= set(payload.get("roles", []) or [])
    return roles

class AuthContext:
    def __init__(self, user: str, email: Optional[str], roles: List[str]):
        self.user = user
        self.email = email
        self.roles = roles

def require_user(
    # Mode gateway (X-Auth-Request-* injectés par Traefik/NGINX forward-auth)
    x_auth_request_user: Optional[str] = Header(
        None, alias="X-Auth-Request-User", convert_underscores=False
    ),
    x_auth_request_email: Optional[str] = Header(
        None, alias="X-Auth-Request-Email", convert_underscores=False
    ),
    x_auth_request_groups: Optional[str] = Header(
        None, alias="X-Auth-Request-Groups", convert_underscores=False
    ),
    # Mode direct : Authorization: Bearer <jwt>
    creds: Optional[HTTPAuthorizationCredentials] = Security(_http_bearer),
) -> AuthContext:
    """
    AuthN/AuthZ combinée :
    - Si la gateway injecte les headers X-Auth-Request-*, on les utilise directement.
    - Sinon, fallback sur un JWT Keycloak (Authorization: Bearer).
    - Sinon, 401 Unauthorized.
    """

    # --- Sécurité pour tests unitaires / appels directs ---
    if not isinstance(x_auth_request_groups, (str, type(None))):
        x_auth_request_groups = None
    if not isinstance(x_auth_request_user, (str, type(None))):
        x_auth_request_user = None
    if not isinstance(x_auth_request_email, (str, type(None))):
        x_auth_request_email = None

    # 1) Mode gateway
    if x_auth_request_user:
        roles = [
            r.strip()
            for r in (x_auth_request_groups or "").split(",")
            if r.strip()
        ]
        return AuthContext(
            user=x_auth_request_user,
            email=x_auth_request_email,
            roles=roles,
        )

    # 2) Mode JWT direct
    if isinstance(creds, HTTPAuthorizationCredentials) and creds.scheme.lower() == "bearer" and creds.credentials:
        try:
            payload = _get_verifier().decode(creds.credentials)
        except Exception:
            logger.warning("JWT invalide (signature/iss/exp)")
            raise HTTPException(status_code=401, detail="JWT invalide")

        user = payload.get("preferred_username") or payload.get("email") or payload.get("sub") or "unknown"
        roles = list(_roles_from_claims(payload))
        return AuthContext(user=user, email=payload.get("email"), roles=roles)

    # 3) Aucun contexte dispo
    raise HTTPException(status_code=401, detail="Unauthorized (no credentials)")


def require_read(auth: AuthContext = Depends(require_user)) -> AuthContext:
    if _ROLE_READ not in auth.roles:
        raise HTTPException(status_code=403, detail=f"forbidden: missing role {_ROLE_READ}")
    return auth

def require_write(auth: AuthContext = Depends(require_user)) -> AuthContext:
    if _ROLE_WRITE not in auth.roles:
        raise HTTPException(status_code=403, detail=f"forbidden: missing role {_ROLE_WRITE}")
    return auth
