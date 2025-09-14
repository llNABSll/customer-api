from __future__ import annotations
import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.models.client import Client
from app.schemas.client import ClientCreate, ClientUpdate

logger = logging.getLogger(__name__)


def _normalize_payload(data: dict) -> dict:
    cc = data.get("country_code")
    if cc:
        data["country_code"] = cc.strip().upper()[:2]
    return data


def create_client(db: Session, client_data: ClientCreate) -> Client:
    try:
        payload = _normalize_payload(client_data.model_dump(exclude_unset=True))
        new_client = Client(**payload)
        db.add(new_client)
        db.commit()
        db.refresh(new_client)
        logger.info("client created", extra={"id": new_client.id, "email": new_client.email})
        return new_client
    except SQLAlchemyError as e:
        db.rollback()
        logger.error("error creating client", exc_info=e)
        raise


def get_client(db: Session, client_id: int) -> Client | None:
    return db.query(Client).filter(Client.id == client_id).first()


def get_clients(db: Session, skip: int = 0, limit: int = 10) -> list[Client]:
    return db.query(Client).offset(skip).limit(limit).all()


def update_client(db: Session, client_id: int, updates: ClientUpdate) -> Client | None:
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        return None
    data = _normalize_payload(updates.model_dump(exclude_unset=True))
    for key, value in data.items():
        setattr(client, key, value)
    db.commit()
    db.refresh(client)
    return client


def delete_client(db: Session, client_id: int) -> Client | None:
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        return None
    db.delete(client)
    db.commit()
    return client
