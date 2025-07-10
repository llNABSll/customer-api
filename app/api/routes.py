# app/api/routes.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.schemas.client import ClientCreate, ClientOut, ClientUpdate          
from app.repositories.client import create_client, get_client, get_clients, update_client, delete_client
from app.core.database import SessionLocal        
from app.core.logger import logger

# Création du routeur 
router = APIRouter()

# Dépendance pour obtenir une session DB puis la fermer proprement
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Route POST pour créer un nouveau client
@router.post("/clients", response_model=ClientOut)
def create_client_endpoint(client_data: ClientCreate, db: Session = Depends(get_db)):
    """
    Crée un nouveau client.
    Renvoie 201 si le client est créé avec succès.
    """
    logger.info(f"Création d'un nouveau client : {client_data.email}")
    try:
        new_client = create_client(db, client_data)
        logger.info(f"Client créé avec succès : {new_client.email}")
        return new_client
    except Exception as e:
        logger.error(f"Erreur lors de la création du client : {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


# Route GET pour récupérer un client par ID
@router.get("/clients/{client_id}", response_model=ClientOut)
def get_client_endpoint(client_id: int, db: Session = Depends(get_db)):
    """
    Récupère un client par son ID.
    Renvoie 404 si le client n’existe pas.
    """
    logger.info(f"Recherche du client id={client_id}")
    client = get_client(db, client_id)

    if not client:
        logger.warning(f"Client id={client_id} introuvable")
        raise HTTPException(status_code=404, detail="Client not found")

    logger.info(f"Client trouvé : {client.email}")
    return client

# Route GET pour lister les clients
@router.get("/clients", response_model=list[ClientOut])
def list_clients_endpoint(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    """
    Liste les clients avec pagination.
    Renvoie 200 avec la liste des clients.
    """
    logger.info(f"Liste des clients : skip={skip}, limit={limit}")
    clients = get_clients(db, skip=skip, limit=limit)
    logger.info(f"{len(clients)} clients trouvés")
    return clients

# Route PUT pour mettre à jour un client
@router.put("/clients/{client_id}", response_model=ClientOut)
def update_client_endpoint(client_id: int, updates: ClientUpdate, db: Session = Depends(get_db)):
    """
    Met à jour un client existant.
    Renvoie 404 si le client n’existe pas.
    """
    logger.info(f"Mise à jour du client id={client_id}")
    updated_client = update_client(db, client_id, updates)

    if not updated_client:
        logger.warning(f"Client id={client_id} non trouvé pour mise à jour")
        raise HTTPException(status_code=404, detail="Client not found")

    logger.info(f"Client mis à jour : {updated_client.email}")
    return updated_client

# Route DELETE pour supprimer un client
@router.delete("/clients/{client_id}", response_model=dict)
def delete_client_endpoint(client_id: int, db: Session = Depends(get_db)):
    """
    Supprime un client par son ID.
    Renvoie 404 si le client n’existe pas.
    """
    logger.info(f"Suppression du client id={client_id}")
    success = delete_client(db, client_id)

    if not success:
        logger.warning(f"Client id={client_id} non trouvé pour suppression")
        raise HTTPException(status_code=404, detail="Client not found")

    logger.info(f"Client id={client_id} supprimé avec succès")
    return {"detail": "Client deleted successfully"}


