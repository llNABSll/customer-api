from __future__ import annotations

import logging
from typing import List, Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status, Header
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.client import ClientCreate, ClientUpdate, ClientResponse
from app.services.client_service import (
    CustomerService,
    NotFoundError,
    EmailAlreadyExistsError,
    ConcurrencyConflictError,
)
from app.main import rabbitmq
from app.security.security import require_read, require_write

router = APIRouter(prefix="/customers", tags=["Customers"])
logger = logging.getLogger(__name__)

# ---------- Messages ----------
CUSTOMER_NOT_FOUND_MSG = "Customer not found"
EMAIL_ALREADY_EXISTS_MSG = "Email already exists"
VERSION_CONFLICT_MSG = "Concurrency conflict"

# ---------- Dépendance CustomerService ----------
def get_customer_service(db: Session = Depends(get_db)) -> CustomerService:
    return CustomerService(db, rabbitmq)

# ===================== CRUD =====================

@router.post(
    "/",
    response_model=ClientResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_write)],
)
async def create_customer(
    customer: ClientCreate,
    svc: CustomerService = Depends(get_customer_service),
):
    """Crée un client (sécurité : rôle écriture requis)."""
    try:
        created = await svc.create(customer)
        logger.info("customer created", extra={"id": created.id, "email": created.email})
        return created
    except EmailAlreadyExistsError:
        logger.debug("email conflict on create", extra={"email": customer.email})
        raise HTTPException(status_code=409, detail=EMAIL_ALREADY_EXISTS_MSG)


@router.get(
    "/",
    response_model=List[ClientResponse],
    dependencies=[Depends(require_read)],
)
def list_customers(
    q: Optional[str] = Query(None, description="Recherche partielle sur prénom/nom/email"),
    company: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    sort_by: Literal["id", "first_name", "last_name", "email", "company", "created_at", "updated_at"] = Query("id"),
    sort_dir: Literal["asc", "desc"] = Query("asc"),
    svc: CustomerService = Depends(get_customer_service),
):
    """Liste paginée avec filtres/tri (sécurité : rôle lecture requis)."""
    rows = svc.list(
        q=q,
        company=company,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    logger.debug("customers listed", extra={"count": len(rows)})
    return rows


@router.get(
    "/{customer_id}",
    response_model=ClientResponse,
    dependencies=[Depends(require_read)],
)
def read_customer(customer_id: int, svc: CustomerService = Depends(get_customer_service)):
    """Détail d’un client par ID (sécurité : rôle lecture requis)."""
    try:
        return svc.get(customer_id)
    except NotFoundError:
        logger.debug("customer not found", extra={"id": customer_id})
        raise HTTPException(status_code=404, detail=CUSTOMER_NOT_FOUND_MSG)


@router.put(
    "/{customer_id}",
    response_model=ClientResponse,
    dependencies=[Depends(require_write)],
)
async def update_customer(
    customer_id: int,
    customer: ClientUpdate,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    svc: CustomerService = Depends(get_customer_service),
):
    """Met à jour un client (optimistic locking via If-Match)."""
    try:
        expected_version = int(if_match) if if_match is not None else None
    except ValueError:
        raise HTTPException(status_code=400, detail="If-Match doit être un entier")

    try:
        updated = await svc.update(customer_id, customer, expected_version=expected_version)
        logger.info("customer updated", extra={"id": customer_id, "version": updated.version})
        return updated
    except NotFoundError:
        raise HTTPException(status_code=404, detail=CUSTOMER_NOT_FOUND_MSG)
    except EmailAlreadyExistsError:
        raise HTTPException(status_code=409, detail=EMAIL_ALREADY_EXISTS_MSG)
    except ConcurrencyConflictError:
        raise HTTPException(status_code=409, detail=VERSION_CONFLICT_MSG)


@router.delete(
    "/{customer_id}",
    response_model=ClientResponse,
    dependencies=[Depends(require_write)],
)
async def delete_customer(customer_id: int, svc: CustomerService = Depends(get_customer_service)):
    """Supprime un client (sécurité : rôle écriture requis)."""
    try:
        deleted = await svc.delete(customer_id)
        logger.info("customer deleted", extra={"id": customer_id})
        return deleted
    except NotFoundError:
        raise HTTPException(status_code=404, detail=CUSTOMER_NOT_FOUND_MSG)

# ===================== Extras =====================

@router.get(
    "/email/{email}",
    response_model=ClientResponse,
    dependencies=[Depends(require_read)],
)
def read_by_email(email: str, svc: CustomerService = Depends(get_customer_service)):
    """Récupère un client par adresse email exacte."""
    customer = svc.get_by_email(email)
    if not customer:
        raise HTTPException(status_code=404, detail=CUSTOMER_NOT_FOUND_MSG)
    return customer
