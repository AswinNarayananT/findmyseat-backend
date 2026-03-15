from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from enum import Enum

class SectionCreateSchema(BaseModel):
    name: str
    price: float
    display_order: int
    color: str

class SeatCreateSchema(BaseModel):
    row_label: Optional[str] = None
    seat_number: Optional[int] = None
    x_position: int
    y_position: int
    seat_type: str  
    section_index: Optional[int] = None

class SeatLayoutCreateSchema(BaseModel):
    rows: int
    columns: int
    event_show_ids: List[UUID]
    sections: List[SectionCreateSchema]
    seats: List[SeatCreateSchema]

