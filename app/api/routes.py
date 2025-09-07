# app/api/routes.py

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from app.schemas.client import ClientCreate, ClientOut, ClientUpdate
from app.repositories import client as repo
from app.core.database import get_db 
from app.core.logger import logger
from app.core.rabbitmq import rabbitmq

router = APIRouter()

EVENT_EXCHANGE = "customer_events"

async def _publish_safe(event: dict) -> None:
    try:
        await rabbitmq.publish(EVENT_EXCHANGE, event)
    except Exception as e:
        logger.error(f"[events] publish failed: {e}")

@router.post("/clients", response_model=ClientOut, status_code=201)
async def create_client_endpoint(client_data: ClientCreate, db: Session = Depends(get_db)):
    """
    Crée un nouveau client et publie 'customer.created'.
    """
    logger.info(f"Création d'un nouveau client : {client_data.email}")
    try:
        # ⬅️ passer le payload (client_data), pas client_id
        new_client = await run_in_threadpool(repo.create_client, db, client_data)

        await _publish_safe({
            "type": "customer.created",
            "source": "customer-api",
            "data": {"id": new_client.id, "email": getattr(new_client, "email", None)}
        })
        logger.info(f"Client créé avec succès : {new_client.email}")
        return new_client
    except Exception as e:
        logger.error(f"Erreur lors de la création du client : {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.get("/clients/{client_id}", response_model=ClientOut)
async def get_client_endpoint(client_id: int, db: Session = Depends(get_db)):
    """
    Récupère un client par son ID.
    """
    logger.info(f"Recherche du client id={client_id}")
    client = await run_in_threadpool(repo.get_client, db, client_id)
    if not client:
        logger.warning(f"Client id={client_id} introuvable")
        raise HTTPException(status_code=404, detail="Client not found")
    logger.info(f"Client trouvé : {client.email}")
    return client

@router.get("/clients", response_model=list[ClientOut])
async def list_clients_endpoint(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    """
    Liste des clients paginée.
    """
    logger.info(f"Liste des clients : skip={skip}, limit={limit}")
    # ⬅️ appeler la bonne fonction + variables cohérentes
    clients = await run_in_threadpool(repo.get_clients, db, skip, limit)
    logger.info(f"{len(clients)} clients trouvés")
    return clients

@router.put("/clients/{client_id}", response_model=ClientOut)
async def update_client_endpoint(client_id: int, updates: ClientUpdate, db: Session = Depends(get_db)):
    """
    Met à jour un client existant et publie 'customer.updated'.
    """
    logger.info(f"Mise à jour du client id={client_id}")
    updated_client = await run_in_threadpool(repo.update_client, db, client_id, updates)
    if not updated_client:
        logger.warning(f"Client id={client_id} non trouvé pour mise à jour")
        raise HTTPException(status_code=404, detail="Client not found")

    await _publish_safe({
        "type": "customer.updated",
        "source": "customer-api",
        "data": {"id": updated_client.id}
    })
    logger.info(f"Client mis à jour : {updated_client.email}")
    return updated_client

@router.delete("/clients/{client_id}", response_model=dict)
async def delete_client_endpoint(client_id: int, db: Session = Depends(get_db)):
    """
    Supprime un client et publie 'customer.deleted'.
    """
    logger.info(f"Suppression du client id={client_id}")
    success = await run_in_threadpool(repo.delete_client, db, client_id)
    if not success:
        logger.warning(f"Client id={client_id} non trouvé pour suppression")
        raise HTTPException(status_code=404, detail="Client not found")

    await _publish_safe({
        "type": "customer.deleted",
        "source": "customer-api",
        "data": {"id": client_id}
    })
    logger.info(f"Client id={client_id} supprimé avec succès")
    return {"detail": "Client deleted successfully"}
