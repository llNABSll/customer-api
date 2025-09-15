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


class NotFoundError(Exception): ...
class EmailAlreadyExistsError(Exception): ...
class ConcurrencyConflictError(Exception): ...


class CustomerService:
    def __init__(self, db: Session, mq: MessagePublisher | None):
        self.db = db
        self.mq = mq

    def get(self, customer_id: int) -> Client:
        c = repo.get_client(self.db, customer_id)
        if not c:
            raise NotFoundError("Customer not found")
        return c

    def get_by_email(self, email: str) -> Optional[Client]:
        return self.db.query(Client).filter(Client.email == email).first()

    def list(
        self,
        q: Optional[str] = None,
        company: Optional[str] = None,
        sort_by: Literal["id", "first_name", "last_name", "email", "company", "created_at", "updated_at"] = "id",
        sort_dir: Literal["asc", "desc"] = "asc",
        skip: int = 0,
        limit: int = 10,
    ) -> list[Client]:
        query = self.db.query(Client)
        if q:
            like = f"%{q}%"
            query = query.filter(
                (Client.first_name.ilike(like)) |
                (Client.last_name.ilike(like)) |
                (Client.email.ilike(like))
            )
        if company:
            query = query.filter(Client.company == company)
        sort_col = getattr(Client, sort_by)
        if sort_dir == "desc":
            sort_col = sort_col.desc()
        return query.order_by(sort_col).offset(skip).limit(limit).all()

    async def create(self, data: ClientCreate) -> Client:
        try:
            customer = repo.create_client(self.db, data)
        except IntegrityError:
            raise EmailAlreadyExistsError("Email already exists")
        if self.mq:
            await self.mq.publish_message(
                "customer.created",
                {
                    "id": customer.id,
                    "email": customer.email,
                    "first_name": customer.first_name,
                    "last_name": customer.last_name,
                },
            )
        return customer

    async def update(
        self,
        customer_id: int,
        data: ClientUpdate,
        expected_version: Optional[int] = None,
    ) -> Client:
        current = repo.get_client(self.db, customer_id)
        if not current:
            raise NotFoundError("Customer not found")
        if expected_version is not None and current.version != expected_version:
            raise ConcurrencyConflictError("Version mismatch")
        try:
            customer = repo.update_client(self.db, customer_id, data)
        except IntegrityError:
            raise EmailAlreadyExistsError("Email already exists")
        except StaleDataError:
            raise ConcurrencyConflictError("Customer modified elsewhere")
        if not customer:
            raise NotFoundError("Customer not found")
        if self.mq:
            await self.mq.publish_message(
                "customer.updated",
                {
                    "id": customer.id,
                    "email": customer.email,
                    "first_name": customer.first_name,
                    "last_name": customer.last_name,
                },
            )
        return customer

    async def delete(self, customer_id: int) -> Client:
        customer = repo.delete_client(self.db, customer_id)
        if not customer:
            raise NotFoundError("Customer not found")
        if self.mq:
            await self.mq.publish_message("customer.deleted", {
                "id": customer_id,
                "email": customer.email,
                "first_name": customer.first_name,
                "last_name": customer.last_name,
            })
        return customer
