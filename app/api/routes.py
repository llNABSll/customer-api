# app/api/routes.py

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from app.schemas.client import ClientCreate, ClientOut, ClientUpdate          
from app.repositories.client import create_client, get_client, get_clients, update_client, delete_client
from app.core.database import SessionLocal        
from app.core.logger import logger
from app.core.rabbitmq import rabbitmq

# Création du routeur 
router = APIRouter()

# Nom de l'échange RabbitMQ pour les événements clients
EVENT_EXCHANGE = "customer_events"

# Dépendance pour obtenir une session DB puis la fermer proprement
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Helper publication “safe” : log l’erreur mais ne casse pas la requête
async def _publish_safe(event: dict) -> None:
    try:
        await rabbitmq.publish(EVENT_EXCHANGE, event)
    except Exception as e:
        logger.error(f"[events] publish failed: {e}")

# Route POST pour créer un nouveau client
@router.post("/clients", response_model=ClientOut, status_code=201)
async def create_client_endpoint(client_data: ClientCreate, db: Session = Depends(get_db)):
    """
    Crée un nouveau client.
    Renvoie 201 si le client est créé avec succès.
    Publie un événement 'customer.created'.
    """
    logger.info(f"Création d'un nouveau client : {client_data.email}")
    try:
        new_client = await run_in_threadpool(create_client, db, client_data)

        # Publication de l'événement de création de client
        await _publish_safe({
            "type": "customer.created",
            "source": "customer-api",
            "data": {
                "id": new_client.id,
                "email": getattr(new_client, "email", None),
            }
        })

        logger.info(f"Client créé avec succès : {new_client.email}")
        return new_client
    except Exception as e:
        logger.error(f"Erreur lors de la création du client : {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


# Route GET pour récupérer un client par ID
@router.get("/clients/{client_id}", response_model=ClientOut)
async def get_client_endpoint(client_id: int, db: Session = Depends(get_db)):
    """
    Récupère un client par son ID.
    Renvoie 404 si le client n’existe pas.
    """
    logger.info(f"Recherche du client id={client_id}")
    client = await run_in_threadpool(get_client, db, client_id)

    # Vérification si le client a été trouvé
    if not client:
        logger.warning(f"Client id={client_id} introuvable")
        raise HTTPException(status_code=404, detail="Client not found")

    logger.info(f"Client trouvé : {client.email}")
    return client

# Route GET pour lister les clients
@router.get("/clients", response_model=list[ClientOut])
async def list_clients_endpoint(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    """
    Liste les clients avec pagination.
    Renvoie 200 avec la liste des clients.
    """
    logger.info(f"Liste des clients : skip={skip}, limit={limit}")
    clients = await run_in_threadpool(get_clients, db, skip, limit)
    logger.info(f"{len(clients)} clients trouvés")
    return clients

# Route PUT pour mettre à jour un client
@router.put("/clients/{client_id}", response_model=ClientOut)
async def update_client_endpoint(client_id: int, updates: ClientUpdate, db: Session = Depends(get_db)):
    """
    Met à jour un client existant.
    Renvoie 404 si le client n’existe pas.
    """
    logger.info(f"Mise à jour du client id={client_id}")
    updated_client = await run_in_threadpool(update_client, db, client_id, updates)

    # Vérification si le client a été trouvé et mis à jour
    if not updated_client:
        logger.warning(f"Client id={client_id} non trouvé pour mise à jour")
        raise HTTPException(status_code=404, detail="Client not found")

    # Publication de l'événement de mise à jour de client
    await _publish_safe({
        "type": "customer.updated",
        "source": "customer-api",
        "data": {"id": updated_client.id}
    })

    logger.info(f"Client mis à jour : {updated_client.email}")
    return updated_client

# Route DELETE pour supprimer un client
@router.delete("/clients/{client_id}", response_model=dict)
async def delete_client_endpoint(client_id: int, db: Session = Depends(get_db)):
    """
    Supprime un client par son ID.
    Renvoie 404 si le client n’existe pas.
    """
    logger.info(f"Suppression du client id={client_id}")
    success = await run_in_threadpool(delete_client, db, client_id)

    # Vérification si la suppression a réussi
    if not success:
        logger.warning(f"Client id={client_id} non trouvé pour suppression")
        raise HTTPException(status_code=404, detail="Client not found")

    # Publication de l'événement de suppression de client
    await _publish_safe({
        "type": "customer.deleted",
        "source": "customer-api",
        "data": {"id": client_id}
    })

    logger.info(f"Client id={client_id} supprimé avec succès")
    return {"detail": "Client deleted successfully"}


