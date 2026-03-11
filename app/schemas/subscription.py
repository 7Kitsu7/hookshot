from pydantic import BaseModel, HttpUrl, Field
from typing import Optional
from datetime import datetime

class SubscriptionBase(BaseModel):
    name: str = Field(..., min_length=1)
    target_url: HttpUrl # Valida que sea una URL real
    event_type: str = Field(..., min_length=1)
    secret: str = Field(..., min_length=8) # Recomendado por seguridad

class SubscriptionCreate(SubscriptionBase):
    pass

class SubscriptionUpdate(BaseModel):
    # Permite actualizar solo campos específicos
    target_url: Optional[HttpUrl] = None
    is_active: Optional[bool] = None

class SubscriptionOut(SubscriptionBase):
    id: str
    is_active: bool
    # Campos para la metadata de Unfurl
    preview_title: Optional[str] = None
    preview_description: Optional[str] = None
    
    class Config:
        from_attributes = True # Permite leer modelos de SQLAlchemy