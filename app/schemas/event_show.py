from typing import List
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID


class VenueCreate(BaseModel):
    name: str
    formatted_address: str
    latitude: float
    longitude: float


class EventShowCreate(BaseModel):
    event_id: UUID
    venue: VenueCreate
    capacity: int
    start_times: List[datetime]


class EventShowResponse(BaseModel):
    id: UUID
    event_id: UUID
    venue_id: UUID
    start_time: datetime
    end_time: datetime
    capacity: int

    class Config:
        from_attributes = True