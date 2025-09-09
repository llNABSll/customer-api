# app/schemas/client_schema.py
from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class ClientBase(BaseModel):
    """
    Schéma commun pour lecture/écriture des clients.
    - Contraintes sur la longueur des champs texte.
    - Validation stricte de l'email.
    """
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    company: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, min_length=5, max_length=32)


class ClientCreate(ClientBase):
    """Payload de création d'un client : identique à ClientBase."""
    pass


class ClientUpdate(BaseModel):
    """
    Mise à jour partielle : tous les champs sont optionnels.
    Seuls ceux fournis seront appliqués.
    """
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    company: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, min_length=5, max_length=32)


class ClientResponse(ClientBase):
    """
    Représentation renvoyée par l'API.
    Inclut les métadonnées techniques.
    """
    id: int
    version: int
    created_at: datetime
    updated_at: datetime

    # Pydantic v2 : active la conversion depuis un ORM (SQLAlchemy)
    model_config = ConfigDict(from_attributes=True)
