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

from pydantic import BaseModel, Field
from uuid import UUID
from typing import List

class BookingRequestSchema(BaseModel):
    show_id: UUID = Field(..., alias="show_id")
    seat_ids: List[UUID] = Field(..., min_length=1, max_length=10)

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "show_id": "5efe2bbc-9522-45dc-8bd0-23f13dff58ff",
                "seat_ids": [
                    "d9cbe0e6-2afa-4402-8568-870a7ad8c0cb",
                    "a1b2c3d4-e5f6-7g8h-9i0j-k1l2m3n4o5p6"
                ]
            }
        }