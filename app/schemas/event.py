from pydantic import BaseModel
from typing import Any, Dict

class EventCreate(BaseModel):
    event_type: str
    payload: Dict[str, Any]