from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import uuid4

from app.database.dependencies import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.organizer_application import OrganizerApplication
from app.schemas.organizer_application import (
    OrganizerApplicationCreate,
    OrganizerApplicationResponse
)

router = APIRouter(prefix="/organizers", tags=["Organizer Applications"])


@router.post(
    "/apply",
    response_model=OrganizerApplicationResponse,
    status_code=status.HTTP_201_CREATED
)
def submit_organizer_application(
    data: OrganizerApplicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    # Prevent duplicate application per user
    existing_user_application = db.query(OrganizerApplication)\
        .filter(OrganizerApplication.user_id == current_user.id)\
        .first()

    if existing_user_application:
        raise HTTPException(
            status_code=400,
            detail="You have already submitted an application"
        )

    existing_email = db.query(OrganizerApplication)\
        .filter(OrganizerApplication.contact_email == data.email)\
        .first()

    if existing_email:
        raise HTTPException(
            status_code=400,
            detail="Application already submitted with this email"
        )

    application = OrganizerApplication(

        user_id=current_user.id,

        organization_name=data.organization_or_individual_name,
        address=data.address,
        contact_name=data.contact_name,
        contact_email=data.email,
        contact_phone=data.phone_number,
        beneficiary_name=data.beneficiary_name,
        account_type=data.account_type,
        bank_name=data.bank_name,
        account_number=data.account_number,
        ifsc_code=data.ifsc_code,
        is_verified=False,
        status="pending"
    )

    db.add(application)
    db.commit()
    db.refresh(application)

    return application
