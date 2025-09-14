# app/repositories/client.py
from __future__ import annotations
import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.models.client import Client
from app.schemas.client import ClientCreate, ClientUpdate

logger = logging.getLogger(__name__)

def _normalize_payload(data: dict) -> dict:
    # Normaliser country_code (upper, 2 lettres)
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
    client = db.query(Client).filter(Client.id == client_id).first()
    if client:
        logger.debug("client retrieved", extra={"id": client_id})
    else:
        logger.debug("client not found", extra={"id": client_id})
    return client

def get_clients(db: Session, skip: int = 0, limit: int = 10) -> list[Client]:
    rows = db.query(Client).offset(skip).limit(limit).all()
    logger.debug("clients listed", extra={"count": len(rows), "skip": skip, "limit": limit})
    return rows

def update_client(db: Session, client_id: int, updates: ClientUpdate) -> Client | None:
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        logger.debug("client not found for update", extra={"id": client_id})
        return None

    data = _normalize_payload(updates.model_dump(exclude_unset=True))
    for key, value in data.items():
        setattr(client, key, value)

    db.commit()
    db.refresh(client)
    logger.info("client updated", extra={"id": client_id, "version": client.version})
    return client

def delete_client(db: Session, client_id: int) -> Client | None:
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        logger.debug("client not found for delete", extra={"id": client_id})
        return None
    db.delete(client)
    db.commit()
    logger.info("client deleted", extra={"id": client_id})
    return client
