# app/repositories/client.py

import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.models.client import Client
from app.schemas.client import ClientCreate, ClientUpdate

logger = logging.getLogger(__name__)


def create_client(db: Session, client_data: ClientCreate) -> Client:
    """Créer un client en base."""
    try:
        # Utilise model_dump() au lieu de dict()
        new_client = Client(**client_data.model_dump())
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
    """Récupérer un client par ID."""
    client = db.query(Client).filter(Client.id == client_id).first()
    if client:
        logger.debug("client retrieved", extra={"id": client_id})
    else:
        logger.debug("client not found", extra={"id": client_id})
    return client


def get_clients(db: Session, skip: int = 0, limit: int = 10) -> list[Client]:
    """Lister les clients avec pagination."""
    clients = db.query(Client).offset(skip).limit(limit).all()
    logger.debug("clients listed", extra={"count": len(clients), "skip": skip, "limit": limit})
    return clients


def update_client(db: Session, client_id: int, updates: ClientUpdate) -> Client | None:
    """Mettre à jour un client et incrémenter sa version."""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        logger.debug("client not found for update", extra={"id": client_id})
        return None

    # Utilise model_dump() au lieu de dict()
    for key, value in updates.model_dump(exclude_unset=True).items():
        setattr(client, key, value)

    # La version est maintenant incrémentée automatiquement par SQLAlchemy

    db.commit()
    db.refresh(client)
    logger.info("client updated", extra={"id": client_id, "version": client.version})
    return client


def delete_client(db: Session, client_id: int) -> Client | None:
    """Supprimer un client et renvoyer l’entité supprimée."""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        logger.debug("client not found for delete", extra={"id": client_id})
        return None

    db.delete(client)
    db.commit()
    logger.info("client deleted", extra={"id": client_id})
    return client