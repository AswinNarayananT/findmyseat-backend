from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import uuid4
from uuid import UUID
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload


from app.database.dependencies import get_db
from app.core.security import get_current_user
from app.models.user import User, UserRole
from app.models.event_show import EventShow
from app.models.organizer_application import OrganizerApplication, OrganizerStatus
from app.schemas.organizer_application import (
    OrganizerApplicationCreate,
    OrganizerApplicationResponse
)
from app.models.seat import Booking, SeatBooking, SeatBookingStatus

router = APIRouter(prefix="/organizers", tags=["Organizer Applications"])

@router.get(
    "/my-application",
    response_model=OrganizerApplicationResponse
)
def get_my_application(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    application = db.query(OrganizerApplication).filter(
        OrganizerApplication.user_id == current_user.id
    ).first()

    if not application:
        raise HTTPException(
            status_code=404,
            detail="No application found for this user."
        )

    return application

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
    app = db.query(OrganizerApplication)\
        .filter(OrganizerApplication.user_id == current_user.id)\
        .first()

    if app:
        if app.status == OrganizerStatus.approved:
            raise HTTPException(status_code=400, detail="You are already an approved organizer.")
        
        if app.status == OrganizerStatus.pending:
            raise HTTPException(status_code=400, detail="You have a pending application. Please wait for review.")

        if app.status == OrganizerStatus.permanently_rejected or app.rejection_count >= 3:
            raise HTTPException(
                status_code=403, 
                detail=f"Application permanently rejected. You have reached the maximum limit of 3 attempts."
            )

        app.organization_name = data.organization_or_individual_name
        app.address = data.address
        app.contact_name = data.contact_name
        app.contact_email = data.email
        app.contact_phone = data.phone_number
        app.beneficiary_name = data.beneficiary_name
        app.account_type = data.account_type
        app.bank_name = data.bank_name
        app.account_number = data.account_number
        app.ifsc_code = data.ifsc_code

        app.status = OrganizerStatus.pending
        app.current_rejection_reason = None 
        
        db.commit()
        db.refresh(app)
        return app

    existing_email = db.query(OrganizerApplication)\
        .filter(OrganizerApplication.contact_email == data.email)\
        .first()

    if existing_email:
        raise HTTPException(
            status_code=400,
            detail="Application already submitted with this email"
        )

    new_application = OrganizerApplication(
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
        status=OrganizerStatus.pending,
        rejection_count=0
    )

    db.add(new_application)
    db.commit()
    db.refresh(new_application)

    return new_application

@router.post("/booking/verify-checkin/{show_id}/{booking_id}")
async def verify_checkin(
    show_id: UUID,
    booking_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in [UserRole.ORGANIZER, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Unauthorized")

    booking = db.query(Booking).options(
        joinedload(Booking.event_show).joinedload(EventShow.event),
        joinedload(Booking.seat_bookings).joinedload(SeatBooking.seat),
        joinedload(Booking.user)
    ).filter(Booking.id == booking_id).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Invalid Ticket")

    # Verify this booking belongs to the scanned show
    if booking.event_show_id != show_id:
        raise HTTPException(status_code=400, detail="Ticket is not valid for this show")

    if current_user.role == UserRole.ORGANIZER:
        if booking.event_show.event.organizer_id != current_user.id:
            raise HTTPException(status_code=403, detail="Unauthorized: You do not own this event")

    if booking.status != SeatBookingStatus.BOOKED:
        raise HTTPException(status_code=400, detail="Ticket not confirmed")

    # if booking.is_checked_in:
    #     time_str = booking.checked_in_at.strftime('%I:%M %p')
    #     raise HTTPException(status_code=400, detail=f"Already checked in at {time_str}")

    # booking.is_checked_in = True
    # booking.checked_in_at = func.now()
    db.commit()

    return {
        "status": "success",
        "message": "Access Granted!",
        "details": {
            "event": booking.event_show.event.title,
            "seats_count": len(booking.seat_bookings),
            "user": booking.user.name,
            "seats": ", ".join([
                f"{sb.seat.row_label}{sb.seat.seat_number}"
                for sb in booking.seat_bookings
            ])
        }
    }