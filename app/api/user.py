from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload, contains_eager
from app.database.dependencies import get_db
from uuid import UUID
from app.models.event import Event
from app.models.event_show import EventShow
from app.models.seat import Seat, SeatLayout, SeatSection, Booking, SeatBooking, SeatBookingStatus
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.models.user import User, UserRole
from app.models.seat import Seat, SeatBooking, SeatBookingStatus, SeatSection
from app.models.finance import Payment, PaymentStatus , Wallet, Transaction, TransactionType
from app.database.dependencies import get_db
from app.core.security import get_current_user
from app.schemas.seat import BookingRequestSchema
from app.services.payment_service import PaymentService
from app.core.config import settings
from sqlalchemy import func

router = APIRouter(prefix="/public/events", tags=["Public Events"])

@router.get("/")
def list_active_events(db: Session = Depends(get_db)):
    now = datetime.now()

    events = db.query(Event).join(Event.shows).join(EventShow.seat_layout).filter(
        Event.is_active == True,
        EventShow.start_time > now,
        EventShow.is_cancelled == False
    ).options(
        contains_eager(Event.shows).options(
            joinedload(EventShow.venue),
            contains_eager(EventShow.seat_layout)
        )
    ).order_by(Event.created_at.desc()).all()

    return events

# @router.get("/{event_id}")
# def get_public_event_details(event_id: UUID, db: Session = Depends(get_db)):
#     event = db.query(Event).options(
#         joinedload(Event.shows).joinedload(EventShow.venue),
#         joinedload(Event.shows).joinedload(EventShow.seat_layout)
#     ).filter(
#         Event.id == event_id,
#         Event.is_active == True 
#     ).first()

#     if not event:
#         raise HTTPException(status_code=404, detail="Event not found or is no longer active")

#     return event


@router.get("/{event_id}")
def get_public_event_details(event_id: UUID, db: Session = Depends(get_db)):
    now = datetime.now()

    event = db.query(Event).join(Event.shows).join(EventShow.seat_layout).filter(
        Event.id == event_id,
        Event.is_active == True,
        EventShow.start_time > now,
        EventShow.is_cancelled == False
    ).options(
        contains_eager(Event.shows).options(
            joinedload(EventShow.venue),
            contains_eager(EventShow.seat_layout).joinedload(SeatLayout.sections)
        )
    ).populate_existing().first()

    if not event:
        raise HTTPException(
            status_code=404, 
            detail="Event not found or has no upcoming shows with ready layouts."
        )

    return event



@router.get("/show/{show_id}/layout")
def get_show_layout_details(show_id: UUID, db: Session = Depends(get_db)):
    show = db.query(EventShow).options(
        joinedload(EventShow.venue),
        joinedload(EventShow.seat_layout).joinedload(SeatLayout.sections),
        joinedload(EventShow.seat_layout)
            .joinedload(SeatLayout.seats)
            .joinedload(Seat.section), 
        joinedload(EventShow.seat_layout)
            .joinedload(SeatLayout.seats)
            .joinedload(Seat.seat_bookings)
            .joinedload(SeatBooking.booking) 
    ).filter(EventShow.id == show_id).first()

    if not show:
        raise HTTPException(status_code=404, detail="Show not found")

    other_shows = db.query(EventShow).filter(
        EventShow.event_id == show.event_id,
        EventShow.id != show_id 
    ).order_by(EventShow.start_time).all()

    return {
        "current_show": show,
        "other_shows": other_shows
    }


@router.post("/booking/confirm-booking")
async def confirm_and_lock_seats(
    payload: BookingRequestSchema, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    now = datetime.now()
    expiry_time = now + timedelta(minutes=10)
    
    try:
        unavailable = db.query(SeatBooking).join(Booking).filter(
            SeatBooking.seat_id.in_(payload.seat_ids),
            Booking.event_show_id == payload.show_id,
            (Booking.status == SeatBookingStatus.BOOKED) |
            ((Booking.status == SeatBookingStatus.LOCKED) & 
             (Booking.locked_until > now) & 
             (Booking.user_id != current_user.id))
        ).all()

        if unavailable:
            raise HTTPException(status_code=400, detail="One or more seats are no longer available.")

        old_bookings = db.query(Booking).filter(
            Booking.user_id == current_user.id,
            Booking.event_show_id == payload.show_id,
            Booking.status == SeatBookingStatus.LOCKED
        ).all()
        
        for old in old_bookings:
            db.delete(old) 
        
        db.flush()

        seats_data = db.query(Seat).join(SeatSection).filter(Seat.id.in_(payload.seat_ids)).all()
        total_amount = sum([float(s.section.price) for s in seats_data])

        razor_order = PaymentService.create_order(amount=int(total_amount * 100))

        new_booking = Booking(
            user_id=current_user.id,
            event_show_id=payload.show_id,
            status=SeatBookingStatus.LOCKED,
            locked_until=expiry_time,

        )
        db.add(new_booking)
        db.flush() 

        for seat_id in payload.seat_ids:
            db.add(SeatBooking(
                booking_id=new_booking.id,
                seat_id=seat_id
            ))

        db.add(Payment(
            user_id=current_user.id,
            razorpay_order_id=razor_order['id'],
            amount=total_amount,
            status=PaymentStatus.PENDING
        ))

        db.commit()

        return {
            "booking_id": str(new_booking.id),
            "order_id": razor_order['id'],
            "amount": total_amount,
            "key_id": settings.RAZORPAY_KEY_ID,
            "expiry": expiry_time
        }

    except Exception as e:
        db.rollback()
        print(f"Error in confirm_booking: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process booking.")
    

@router.get("/booking/my-active-lock")
def get_active_user_lock(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    now = datetime.now()

    active_booking = db.query(Booking).options(
        joinedload(Booking.seat_bookings)
    ).filter(
        Booking.user_id == current_user.id,
        Booking.status == SeatBookingStatus.LOCKED,
        Booking.locked_until > now
    ).order_by(Booking.created_at.desc()).first()

    if not active_booking:
        return {"has_active_lock": False}

    latest_payment = db.query(Payment).filter(
        Payment.user_id == current_user.id,
        Payment.status == PaymentStatus.PENDING
    ).order_by(Payment.created_at.desc()).first()

    return {
        "has_active_lock": True,
        "booking_id": str(active_booking.id),
        "show_id": str(active_booking.event_show_id),
        "seat_count": len(active_booking.seat_bookings),
        "expires_at": active_booking.locked_until,
        "total_price": float(latest_payment.amount) if latest_payment else 0,
        "razorpay_order_id": latest_payment.razorpay_order_id if latest_payment else None
    }

@router.post("/booking/verify-payment")
async def verify_payment(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    is_valid = PaymentService.verify_payment(
        payload['razorpay_order_id'],
        payload['razorpay_payment_id'],
        payload['razorpay_signature']
    )

    if not is_valid:
        raise HTTPException(status_code=400, detail="Payment verification failed.")

    try:
        payment = db.query(Payment).filter(Payment.razorpay_order_id == payload['razorpay_order_id']).first()
        if not payment:
            raise HTTPException(status_code=404, detail="Payment record not found.")
            
        payment.status = PaymentStatus.CAPTURED
        payment.razorpay_payment_id = payload['razorpay_payment_id']
        payment.razorpay_signature = payload['razorpay_signature']

        booking = db.query(Booking).options(
            joinedload(Booking.seat_bookings)
        ).filter(
            Booking.user_id == current_user.id,
            Booking.status == SeatBookingStatus.LOCKED,
            Booking.locked_until > datetime.now()
        ).order_by(Booking.created_at.desc()).first()

        if not booking:
             raise HTTPException(status_code=400, detail="No active locks found. Session may have expired.")

        booking.status = SeatBookingStatus.BOOKED
        booking.booked_at = func.now()

        admin = db.query(User).options(joinedload(User.wallet)).filter(User.role == UserRole.ADMIN).first()
        
        if not admin or not admin.wallet:
            raise HTTPException(status_code=500, detail="Admin wallet system not found.")

        db.add(Transaction(
            payment_id=payment.id,
            receiver_wallet_id=admin.wallet.id,
            amount=payment.amount,
            tx_type=TransactionType.BOOKING,
            description=f"Booking ID: {booking.id} - {len(booking.seat_bookings)} seats"
        ))

        admin.wallet.balance = float(admin.wallet.balance) + float(payment.amount)

        db.commit()
        return {
            "status": "success", 
            "message": "Tickets booked successfully!", 
            "booking_id": str(booking.id)
        }

    except Exception as e:
        db.rollback()
        print(f"VERIFY ERROR: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail="Internal Server Error during verification.")


@router.get("/booking/my-bookings")
def get_user_bookings(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        bookings = (
            db.query(Booking)
            .options(
                joinedload(Booking.event_show).joinedload(EventShow.event),
                joinedload(Booking.event_show).joinedload(EventShow.venue),
                joinedload(Booking.seat_bookings).joinedload(SeatBooking.seat).joinedload(Seat.section),
            )
            .filter(
                Booking.user_id == current_user.id,
                Booking.status == SeatBookingStatus.BOOKED 
            )
            .order_by(Booking.created_at.desc())
            .all()
        )

        return [
            {
                "id": str(b.id),
                "event_show_id": str(b.event_show_id),
                "event_name": b.event_show.event.title,
                "event_image": b.event_show.event.image_url,
                "event_date": b.event_show.start_time.strftime("%d %b %Y"),
                "show_time": b.event_show.start_time.strftime("%I:%M %p"),
                "venue_name": b.event_show.venue.name,
                "venue_address": b.event_show.venue.formatted_address,
                "status": b.status.value,            
                "is_checked_in": b.is_checked_in,
                "checked_in_at": b.checked_in_at,
                "total_seats": len(b.seat_bookings),
                "seats": [
                    {
                        "booking_id": str(sb.id),
                        "seat_label": f"{sb.seat.row_label}{sb.seat.seat_number}" if sb.seat.row_label else str(sb.seat.seat_number),
                        "section_name": sb.seat.section.name,
                    }
                    for sb in b.seat_bookings
                ],
                "created_at": b.created_at,
            }
            for b in bookings
        ]

    except Exception as e:
        print(f"CRITICAL API ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

