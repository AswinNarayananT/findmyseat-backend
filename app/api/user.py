from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from app.database.dependencies import get_db
from sqlalchemy.orm import Session, joinedload
from uuid import UUID
from app.models.event import Event
from app.models.event_show import EventShow
from app.models.seat import Seat, SeatLayout, SeatSection
from typing import List
import razorpay
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
    """
    Fetch all active events with their associated shows and venues.
    """
    events = db.query(Event).options(
        joinedload(Event.shows).joinedload(EventShow.venue)
    ).filter(
        Event.is_active == True
    ).order_by(Event.created_at.desc()).all()

    return events

@router.get("/{event_id}")
def get_public_event_details(event_id: UUID, db: Session = Depends(get_db)):
    event = db.query(Event).options(
        joinedload(Event.shows).joinedload(EventShow.venue),
        joinedload(Event.shows).joinedload(EventShow.seat_layout)
    ).filter(
        Event.id == event_id,
        Event.is_active == True 
    ).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found or is no longer active")

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
            .joinedload(Seat.bookings)
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
    try:
        # 1. First, check if the NEW seats are available
        unavailable = db.query(SeatBooking).filter(
            SeatBooking.seat_id.in_(payload.seat_ids),
            SeatBooking.event_show_id == payload.show_id,
            (SeatBooking.status == SeatBookingStatus.BOOKED) |
            ((SeatBooking.status == SeatBookingStatus.LOCKED) & 
             (SeatBooking.locked_until > now) & 
             (SeatBooking.user_id != current_user.id)) # Ignore user's own locks
        ).all()

        if unavailable:
            raise HTTPException(status_code=400, detail="Seats no longer available.")

        # 2. Clear ONLY the user's previous locks for this specific show
        db.query(SeatBooking).filter(
            SeatBooking.user_id == current_user.id,
            SeatBooking.status == SeatBookingStatus.LOCKED
        ).delete()
        db.flush()

        # 3. Calculate Price
        seats_data = db.query(Seat).join(SeatSection).filter(Seat.id.in_(payload.seat_ids)).all()
        total_amount = sum([float(s.section.price) for s in seats_data])

        # 4. Create External Order
        razor_order = PaymentService.create_order(amount=int(total_amount * 100))

        # 5. Create new Locks
        expiry_time = now + timedelta(minutes=10)
        for seat_id in payload.seat_ids:
            db.add(SeatBooking(
                seat_id=seat_id,
                event_show_id=payload.show_id,
                user_id=current_user.id,
                status=SeatBookingStatus.LOCKED,
                locked_until=expiry_time
            ))

        db.add(Payment(
            user_id=current_user.id,
            razorpay_order_id=razor_order['id'],
            amount=total_amount,
            status=PaymentStatus.PENDING
        ))

        db.commit()
        return {
            "order_id": razor_order['id'],
            "amount": total_amount,
            "key_id": settings.RAZORPAY_KEY_ID,
            "expiry": expiry_time
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    

from sqlalchemy.orm import joinedload # Add this import
@router.get("/booking/my-active-lock")
def get_active_user_lock(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    now = datetime.now()

    active_locks = db.query(SeatBooking).filter(
        SeatBooking.user_id == current_user.id,
        SeatBooking.status == SeatBookingStatus.LOCKED,
        SeatBooking.locked_until > now
    ).all()

    if not active_locks:
        return {"has_active_lock": False}

    # IMPORTANT: We need the Payment record to get the Order ID and Price
    # We find the latest PENDING payment for this user
    latest_payment = db.query(Payment).filter(
        Payment.user_id == current_user.id,
        Payment.status == PaymentStatus.PENDING
    ).order_by(Payment.created_at.desc()).first()

    return {
        "has_active_lock": True,
        "show_id": active_locks[0].event_show_id,
        "seat_count": len(active_locks),
        "expires_at": min([l.locked_until for l in active_locks]),
        # Add these fields so the frontend doesn't crash or show "No Session"
        "total_price": float(latest_payment.amount) if latest_payment else 0,
        "razorpay_order_id": latest_payment.razorpay_order_id if latest_payment else None
    }

@router.post("/booking/verify-payment")
async def verify_payment(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 1. Verify Signature
    is_valid = PaymentService.verify_payment(
        payload['razorpay_order_id'],
        payload['razorpay_payment_id'],
        payload['razorpay_signature']
    )

    if not is_valid:
        raise HTTPException(status_code=400, detail="Payment verification failed.")

    try:
        # 2. Update Payment
        payment = db.query(Payment).filter(Payment.razorpay_order_id == payload['razorpay_order_id']).first()
        if not payment:
            raise HTTPException(status_code=404, detail="Payment record not found.")
            
        payment.status = PaymentStatus.CAPTURED
        payment.razorpay_payment_id = payload['razorpay_payment_id']
        payment.razorpay_signature = payload['razorpay_signature']

        # 3. Process Bookings
        bookings = db.query(SeatBooking).filter(
            SeatBooking.user_id == current_user.id,
            SeatBooking.status == SeatBookingStatus.LOCKED,
            SeatBooking.locked_until > datetime.now()
        ).all()

        if not bookings:
             raise HTTPException(status_code=400, detail="No active locks found. Perhaps time expired?")

        for b in bookings:
            b.status = SeatBookingStatus.BOOKED
            b.booked_at = func.now()

        # 4. FIX: Use joinedload to fetch Admin and Wallet in ONE query
        admin = db.query(User).options(joinedload(User.wallet)).filter(User.role == UserRole.ADMIN).first()
        
        if not admin or not admin.wallet:
            raise HTTPException(status_code=500, detail="Admin wallet system not found.")

        # 5. Internal Ledger
        db.add(Transaction(
            payment_id=payment.id,
            receiver_wallet_id=admin.wallet.id,
            amount=payment.amount,
            tx_type=TransactionType.BOOKING,
            description=f"Booking for {len(bookings)} seats"
        ))
        
        # Perform the balance update
        admin.wallet.balance = float(admin.wallet.balance) + float(payment.amount)

        db.commit()
        return {"status": "success", "message": "Tickets booked successfully!"}

    except Exception as e:
        db.rollback()
        # Log the actual error to your terminal so you can see it
        print(f"VERIFY ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error during verification.")
