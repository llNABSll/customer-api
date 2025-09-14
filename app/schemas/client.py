from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict, model_validator

class ClientBase(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name:  Optional[str] = Field(None, min_length=1, max_length=100)

    email:   EmailStr
    company: Optional[str] = Field(None, max_length=255)
    phone:   Optional[str] = Field(None, min_length=5, max_length=32)

    address_line1: Optional[str] = Field(None, max_length=200)
    address_line2: Optional[str] = Field(None, max_length=200)
    postal_code:   Optional[str] = Field(None, max_length=20)
    city:          Optional[str] = Field(None, max_length=100)
    state:         Optional[str] = Field(None, max_length=100)
    country_code:  Optional[str] = Field(None, min_length=2, max_length=2, description="ISO 3166-1 alpha-2 (ex: FR)")

class ClientCreate(ClientBase):
    @model_validator(mode="after")
    def _ensure_name_present(self):
        if not (self.first_name or self.last_name):
            raise ValueError("Provide at least 'first_name' or 'last_name'.")
        return self

class ClientUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name:  Optional[str] = Field(None, min_length=1, max_length=100)
    email:      Optional[EmailStr] = None
    company:    Optional[str] = Field(None, max_length=255)
    phone:      Optional[str] = Field(None, min_length=5, max_length=32)

    address_line1: Optional[str] = Field(None, max_length=200)
    address_line2: Optional[str] = Field(None, max_length=200)
    postal_code:   Optional[str] = Field(None, max_length=20)
    city:          Optional[str] = Field(None, max_length=100)
    state:         Optional[str] = Field(None, max_length=100)
    country_code:  Optional[str] = Field(None, min_length=2, max_length=2)

class ClientResponse(ClientBase):
    id: int
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)