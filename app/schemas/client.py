# app/schemas/client.py

from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional


class ClientBase(BaseModel):
    name: str
    email: EmailStr
    company: Optional[str] = None
    phone: Optional[str] = None

class ClientCreate(ClientBase):
    pass

class ClientUpdate(ClientBase):
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class ClientOut(ClientBase):
    id: int

    class Config:
        orm_mode = True
