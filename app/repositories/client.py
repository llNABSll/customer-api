# app/repositories/client.py

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.models.client import Client
from app.schemas.client import ClientCreate, ClientUpdate
from app.core.logger import logger


def create_client(db: Session, client_data: ClientCreate) -> Client:
    try:
        new_client = Client(**client_data.dict())
        db.add(new_client)
        db.commit()
        db.refresh(new_client)
        logger.info(f"Client créé : {new_client.email}")
        return new_client
    except SQLAlchemyError as e:
        logger.error(f"Erreur lors de la création du client : {e}")
        db.rollback()
        raise


def get_client(db: Session, client_id: int) -> Client:
    client = db.query(Client).filter(Client.id == client_id).first()
    if client:
        logger.info(f"Client récupéré (id={client_id})")
    else:
        logger.warning(f"Client introuvable (id={client_id})")
    return client


def get_clients(db: Session, skip: int = 0, limit: int = 10):
    logger.info(f"Liste des clients : skip={skip}, limit={limit}")
    return db.query(Client).offset(skip).limit(limit).all()


def update_client(db: Session, client_id: int, updates: ClientUpdate) -> Client:
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        logger.warning(f"Client non trouvé pour mise à jour (id={client_id})")
        return None
    for key, value in updates.dict(exclude_unset=True).items():
        setattr(client, key, value)
    db.commit()
    db.refresh(client)
    logger.info(f"Client mis à jour (id={client_id})")
    return client


def delete_client(db: Session, client_id: int) -> bool:
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        logger.warning(f"Client non trouvé pour suppression (id={client_id})")
        return False
    db.delete(client)
    db.commit()
    logger.info(f"Client supprimé (id={client_id})")
    return True
