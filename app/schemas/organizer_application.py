from pydantic import BaseModel, EmailStr
from uuid import UUID
from datetime import datetime
from enum import Enum
from typing import Optional
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
    rejection_reason: Optional[str] = None   
    created_at: datetime                     
    updated_at: Optional[datetime] = None   

    class Config:
        from_attributes = True


class OrganizerStatusUpdate(BaseModel):
    status: OrganizerStatus
    rejection_reason: Optional[str] = None