from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID, uuid4
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from datetime import datetime, timezone


from app.database.dependencies import get_db
from app.core.security import get_current_user
from app.models.user import User, UserRole
from app.models.event import Event
from app.models.event_show import EventShow
from app.models.organizer_application import OrganizerApplication, OrganizerStatus
from app.models.finance import Wallet, Transaction, TransactionType
from app.schemas.organizer_application import (
    OrganizerApplicationCreate,
    OrganizerApplicationResponse
)
from app.schemas.event import CancelReasonRequest
from app.schemas.event_show import VenueUpdate, ShowTimeUpdate
from app.models.seat import Booking, SeatBooking, SeatBookingStatus
from app.models.venue import Venue
from datetime import timedelta
from app.core.notifications import manager

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


@router.get("/revenue-summary")
def get_organizer_revenue_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != UserRole.ORGANIZER:
        raise HTTPException(status_code=403, detail="Unauthorized")

    now = datetime.now(timezone.utc)

    events = db.query(Event).options(
        joinedload(Event.shows)
    ).filter(Event.organizer_id == current_user.id).all()

    total_gross_revenue = 0.0
    total_claimable = 0.0
    event_details = []

    for event in events:
        event_revenue = 0.0
        event_claimable = 0.0
        show_details = []

        for show in event.shows:
            gross = float(show.total_revenue_collected)
            organizer_share = gross * 0.90

            status = "completed" if show.start_time < now else "upcoming"
            
            show_info = {
                "show_id": str(show.id),
                "start_time": show.start_time,
                "gross_revenue": gross,
                "organizer_share": organizer_share,
                "is_payout_processed": show.is_payout_processed,
                "status": status
            }

            event_revenue += gross
            
            if show.start_time < now and not show.is_payout_processed:
                event_claimable += organizer_share
            
            show_details.append(show_info)

        event_details.append({
            "event_id": str(event.id),
            "event_title": event.title,
            "total_event_revenue": event_revenue,
            "event_claimable_amount": event_claimable,
            "shows": show_details
        })

        total_gross_revenue += event_revenue
        total_claimable += event_claimable

    return {
        "summary": {
            "total_gross_revenue": total_gross_revenue,
            "total_organizer_share": total_gross_revenue * 0.90,
            "total_admin_commission": total_gross_revenue * 0.10,
            "total_claimable_now": total_claimable
        },
        "events": event_details
    }


@router.post("/organizer/claim-revenue")
def claim_organizer_revenue(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != UserRole.ORGANIZER:
        raise HTTPException(status_code=403, detail="Unauthorized")

    now = datetime.now(timezone.utc)

    eligible_shows = db.query(EventShow).join(Event).filter(
        Event.organizer_id == current_user.id,
        EventShow.start_time < now,
        EventShow.is_payout_processed == False,
        EventShow.total_revenue_collected > 0
    ).all()

    if not eligible_shows:
        raise HTTPException(status_code=400, detail="No claimable revenue found for completed events.")

    total_gross = sum(float(s.total_revenue_collected) for s in eligible_shows)
    claim_amount = total_gross * 0.90

    admin = db.query(User).options(joinedload(User.wallet)).filter(User.role == UserRole.ADMIN).first()
    organizer_wallet = db.query(Wallet).filter(Wallet.user_id == current_user.id).first()

    if not admin or not admin.wallet or not organizer_wallet:
        raise HTTPException(status_code=500, detail="Wallet system error")

    admin.wallet.balance = float(admin.wallet.balance) - claim_amount
    organizer_wallet.balance = float(organizer_wallet.balance) + claim_amount

    new_tx = Transaction(
        sender_wallet_id=admin.wallet.id,
        receiver_wallet_id=organizer_wallet.id,
        amount=claim_amount,
        tx_type=TransactionType.PAYOUT,
        description=f"Revenue claim for {len(eligible_shows)} completed shows (90% of ₹{total_gross})"
    )
    db.add(new_tx)

    for show in eligible_shows:
        show.is_payout_processed = True

    try:
        db.commit()
        return {
            "status": "success",
            "claimed_amount": claim_amount,
            "processed_shows_count": len(eligible_shows),
            "new_wallet_balance": organizer_wallet.balance
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to process claim")
    

@router.post("/show/{show_id}/cancel")
async def cancel_event_show(
    show_id: UUID,
    reason: CancelReasonRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    show = db.query(EventShow).join(Event).filter(
        EventShow.id == show_id,
        Event.organizer_id == current_user.id
    ).first()

    if not show:
        raise HTTPException(status_code=404, detail="Show not found")
    if show.is_cancelled:
        raise HTTPException(status_code=400, detail="Show already cancelled")
    if show.event.is_active is False:
        raise HTTPException(status_code=400, detail="Cannot cancel a show for an inactive event")
    if show.is_payout_processed:
        raise HTTPException(status_code=400, detail="Cannot cancel after revenue is claimed")

    now = datetime.now(timezone.utc)
    if show.start_time < now:
        raise HTTPException(status_code=400, detail="Cannot cancel a show that has already started or passed")

    bookings = db.query(Booking).filter(
        Booking.event_show_id == show_id,
        Booking.status == SeatBookingStatus.BOOKED
    ).all()

    admin = db.query(User).filter(User.role == UserRole.ADMIN).first()

    for booking in bookings:
        refund_amount = float(booking.total_price) 
        user_wallet = db.query(Wallet).filter(Wallet.user_id == booking.user_id).first()

        admin.wallet.balance = float(admin.wallet.balance) - refund_amount
        user_wallet.balance = float(user_wallet.balance) + refund_amount

        db.add(Transaction(
            sender_wallet_id=admin.wallet.id,
            receiver_wallet_id=user_wallet.id,
            amount=refund_amount,
            tx_type=TransactionType.REFUND,
            description=f"Refund for cancelled show: {show.event.title}"
        ))

        booking.status = SeatBookingStatus.CANCELLED
        for sb in booking.seat_bookings:
            sb.status = SeatBookingStatus.CANCELLED

    show.is_cancelled = True
    show.cancellation_reason = reason.reason

    unique_users = len(set(b.user_id for b in bookings))

    try:
        db.commit()
        
        for uid in set(b.user_id for b in bookings):
            await manager.send_personal_message({
                "type": "SHOW_CANCELLED",
                "title": "Show Cancelled",
                "message": f"Show for {show.event.title} has been cancelled. Refund initiated."
            }, str(uid))
            
        return {
            "status": "success",
            "message": f"Show cancelled. {len(bookings)} bookings refunded for {unique_users} users.",
            "refunded_bookings_count": len(bookings),
            "refunded_users_count": unique_users
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Refund processing failed")
    
@router.post("/event/{event_id}/cancel")
async def cancel_full_event(
    event_id: UUID,
    reason: CancelReasonRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    event = db.query(Event).filter(
        Event.id == event_id,
        Event.organizer_id == current_user.id
    ).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    if event.is_cancelled:
        raise HTTPException(status_code=400, detail="Event is already cancelled")
    
    if not event.is_active:
        raise HTTPException(status_code=400, detail="Event is already inactive")

    shows = db.query(EventShow).filter(
        EventShow.event_id == event_id,
        EventShow.is_cancelled == False
    ).all()

    now = datetime.now(timezone.utc)
    if shows and all(show.start_time < now for show in shows):
        raise HTTPException(status_code=400, detail="Cannot cancel an event where all shows have already passed")

    admin = db.query(User).filter(User.role == UserRole.ADMIN).first()
    total_refunded_bookings = 0
    unique_users_set = set()

    for show in shows:
        if show.is_payout_processed:
            continue

        bookings = db.query(Booking).filter(
            Booking.event_show_id == show.id,
            Booking.status == SeatBookingStatus.BOOKED
        ).all()

        for booking in bookings:
            unique_users_set.add(booking.user_id)
            refund_amount = float(booking.total_price)
            user_wallet = db.query(Wallet).filter(Wallet.user_id == booking.user_id).first()

            admin.wallet.balance = float(admin.wallet.balance) - refund_amount
            user_wallet.balance = float(user_wallet.balance) + refund_amount

            db.add(Transaction(
                sender_wallet_id=admin.wallet.id,
                receiver_wallet_id=user_wallet.id,
                amount=refund_amount,
                tx_type=TransactionType.REFUND,
                description=f"Full event cancellation refund: {event.title}"
            ))

            booking.status = SeatBookingStatus.CANCELLED
            for sb in booking.seat_bookings:
                sb.status = SeatBookingStatus.CANCELLED
            
            total_refunded_bookings += 1

        show.is_cancelled = True
        show.cancellation_reason = reason.reason

    event.is_cancelled = True
    event.cancellation_reason = reason.reason
    event.is_active = False

    try:
        db.commit()
        
        for uid in unique_users_set:
            await manager.send_personal_message({
                "type": "EVENT_CANCELLED",
                "title": "Event Cancelled",
                "message": f"Event {event.title} has been cancelled. Refund initiated."
            }, str(uid))

        return {
            "status": "success", 
            "message": f"Event and {len(shows)} shows cancelled. {total_refunded_bookings} bookings refunded for {len(unique_users_set)} users.",
            "refunded_bookings_count": total_refunded_bookings,
            "refunded_users_count": len(unique_users_set)
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to process full event cancellation")

@router.put("/event/{event_id}/location")
async def update_event_location(
    event_id: UUID,
    payload: VenueUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    event = db.query(Event).filter(
        Event.id == event_id,
        Event.organizer_id == current_user.id
    ).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    shows = db.query(EventShow).filter(EventShow.event_id == event_id).all()
    if not shows:
        raise HTTPException(status_code=400, detail="No shows found for this event")
    
    venue_ids = {show.venue_id for show in shows}
    venues = db.query(Venue).filter(Venue.id.in_(venue_ids)).all()

    for venue in venues:
        venue.name = payload.name
        venue.formatted_address = payload.formatted_address
        venue.latitude = payload.latitude
        venue.longitude = payload.longitude

    try:
        db.commit()

        # Notify users who booked any show of this event
        bookings = db.query(Booking).join(EventShow).filter(
            EventShow.event_id == event_id,
            Booking.status == SeatBookingStatus.BOOKED
        ).all()
        unique_users = set(b.user_id for b in bookings)
        
        for uid in unique_users:
            await manager.send_personal_message({
                "type": "LOCATION_CHANGED",
                "title": "Venue Updated",
                "message": f"The location for {event.title} has been updated."
            }, str(uid))

        return {"status": "success", "message": "Event location updated successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update event location")

@router.put("/show/{show_id}/time")
async def update_show_time(
    show_id: UUID,
    payload: ShowTimeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    show = db.query(EventShow).join(Event).filter(
        EventShow.id == show_id,
        Event.organizer_id == current_user.id
    ).first()

    if not show:
        raise HTTPException(status_code=404, detail="Show not found")
    
    if show.is_cancelled:
        raise HTTPException(status_code=400, detail="Cannot update time for a cancelled show")

    duration = show.event.estimated_duration_minutes
    show.start_time = payload.start_time
    show.end_time = payload.start_time + timedelta(minutes=duration)

    try:
        db.commit()
        
        # Notify users who booked this show
        bookings = db.query(Booking).filter(
            Booking.event_show_id == show_id,
            Booking.status == SeatBookingStatus.BOOKED
        ).all()
        unique_users = set(b.user_id for b in bookings)

        formatted_time = show.start_time.strftime("%d %b %Y, %I:%M %p")
        for uid in unique_users:
            await manager.send_personal_message({
                "type": "TIME_CHANGED",
                "title": "Schedule Updated",
                "message": f"The timing for {show.event.title} has been updated to {formatted_time}."
            }, str(uid))

        return {"status": "success", "message": "Show time updated successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update show time")