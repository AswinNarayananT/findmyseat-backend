import uuid
from typing import Optional
from pydantic import BaseModel, Field
from app.models.event import EntryType, EventCategory


class EventCreate(BaseModel):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    entry_type: EntryType
    category: EventCategory = EventCategory.OTHER
    estimated_duration_minutes: int
    base_price: float
    image_url: Optional[str] = None


class EventResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: Optional[str]
    entry_type: EntryType
    category: EventCategory
    estimated_duration_minutes: int
    base_price: float
    image_url: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True