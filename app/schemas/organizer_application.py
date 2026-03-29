from pydantic import BaseModel, EmailStr
from uuid import UUID
from datetime import datetime
from typing import Optional, List, Any
from app.models.organizer_application import OrganizerStatus

class OrganizerApplicationCreate(BaseModel):
    organization_or_individual_name: str
    address: str
    contact_name: str
    email: EmailStr
    phone_number: str
    beneficiary_name: str
    account_type: str
    bank_name: str
    account_number: str
    ifsc_code: str

class OrganizerApplicationHistoryResponse(BaseModel):
    id: UUID
    rejection_reason: str
    snapshot_data: Optional[Any] = None
    rejected_at: datetime

    class Config:
        from_attributes = True

class OrganizerApplicationResponse(BaseModel):
    id: UUID
    user_id: UUID
    organization_name: str
    address: str
    contact_name: str
    contact_email: EmailStr
    contact_phone: str
    beneficiary_name: str
    account_type: str
    bank_name: str
    account_number: str
    ifsc_code: str
    is_verified: bool
    status: OrganizerStatus
    current_rejection_reason: Optional[str] = None
    rejection_count: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    history: List[OrganizerApplicationHistoryResponse] = []

    class Config:
        from_attributes = True

class OrganizerStatusUpdate(BaseModel):
    status: OrganizerStatus
    rejection_reason: Optional[str] = None