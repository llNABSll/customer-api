# app/services/client_service.py

from __future__ import annotations

import logging
from typing import Optional, Literal
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from app.models.client import Client
from app.schemas.client import ClientCreate, ClientUpdate
from app.repositories import client as repo
from app.infra.events.contracts import MessagePublisher

logger = logging.getLogger(__name__)

# ---------- Exceptions métier ----------
class NotFoundError(Exception):
    pass

class EmailAlreadyExistsError(Exception):
    pass

class ConcurrencyConflictError(Exception):
    """Optimistic locking : entité modifiée ailleurs."""
    pass

# ---------- Service ----------
class CustomerService:
    """
    Couche métier pour Customer.
    Orchestration repository + règles de gestion + publication d’événements.
    """

    def __init__(self, db: Session, mq: MessagePublisher):
        self.db = db
        self.mq = mq

    # ----- READ -----
    def get(self, customer_id: int) -> Client:
        c = repo.get_client(self.db, customer_id)
        if not c:
            logger.debug("customer not found", extra={"id": customer_id})
            raise NotFoundError("Customer not found")
        return c

    def get_by_email(self, email: str) -> Optional[Client]:
        c = self.db.query(Client).filter(Client.email == email).first()
        if not c:
            logger.debug("customer not found by email", extra={"email": email})
            return None
        return c

    def list(
        self,
        q: Optional[str] = None,
        company: Optional[str] = None,
        sort_by: Literal["id", "name", "email", "company", "created_at"] = "id",
        sort_dir: Literal["asc", "desc"] = "asc",
        skip: int = 0,
        limit: int = 10,
    ) -> list[Client]:
        query = self.db.query(Client)

        if q:
            query = query.filter(Client.name.ilike(f"%{q}%") | Client.email.ilike(f"%{q}%"))
        if company:
            query = query.filter(Client.company == company)

        # Tri dynamique
        sort_col = getattr(Client, sort_by)
        if sort_dir == "desc":
            sort_col = sort_col.desc()
        query = query.order_by(sort_col)

        return query.offset(skip).limit(limit).all()

    # ----- CREATE -----
    async def create(self, data: ClientCreate) -> Client:
        try:
            customer = repo.create_client(self.db, data)
        except IntegrityError:
            logger.debug("create conflict: email already exists", extra={"email": data.email})
            raise EmailAlreadyExistsError("Email already exists")

        await self.mq.publish_message(
            "customer.created",
            {"id": customer.id, "name": customer.name, "email": customer.email},
        )
        logger.info("customer created", extra={"id": customer.id})
        return customer

    # ----- UPDATE -----
    async def update(
        self,
        customer_id: int,
        data: ClientUpdate,
        expected_version: Optional[int] = None,
    ) -> Client:
        current = repo.get_client(self.db, customer_id)
        if not current:
            logger.debug("update: customer not found", extra={"id": customer_id})
            raise NotFoundError("Customer not found")

        # Vérification de version pour optimistic locking
        if expected_version is not None and current.version != expected_version:
            logger.debug(
                "update conflict: version mismatch",
                extra={"id": customer_id, "expected": expected_version, "actual": current.version},
            )
            raise ConcurrencyConflictError("Customer has been modified elsewhere")

        try:
            customer = repo.update_client(self.db, customer_id, data)
        except IntegrityError:
            logger.debug("update conflict: email already exists", extra={"email": data.email})
            raise EmailAlreadyExistsError("Email already exists")
        except StaleDataError:
            logger.debug("update conflict: stale data", extra={"id": customer_id})
            raise ConcurrencyConflictError("Customer has been modified elsewhere")

        await self.mq.publish_message(
            "customer.updated",
            {"id": customer.id, "name": customer.name, "email": customer.email},
        )
        logger.info("customer updated", extra={"id": customer.id})
        return customer

    # ----- DELETE -----
    async def delete(self, customer_id: int) -> Client:
        customer = repo.delete_client(self.db, customer_id)
        if not customer:
            logger.debug("delete: customer not found", extra={"id": customer_id})
            raise NotFoundError("Customer not found")

        await self.mq.publish_message("customer.deleted", {"id": customer_id})
        logger.info("customer deleted", extra={"id": customer_id})
        return customer
