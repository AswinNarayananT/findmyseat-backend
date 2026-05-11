from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload, contains_eager
from datetime import timedelta, datetime, timezone
from typing import List
from uuid import UUID

from app.database.dependencies import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.event import Event, Review
from app.models.event_show import EventShow
from app.models.venue import Venue
from app.models.seat import Booking, SeatLayout, SeatBooking, SeatBookingStatus
from app.schemas.event import EventCreate, EventResponse, ReviewCreate
from app.schemas.event_show import EventShowCreate, EventShowResponse


router = APIRouter(prefix="/events", tags=["Events"])


@router.get("/my-events", response_model=list[EventResponse])
def get_my_events(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    events = db.query(Event).filter(
        Event.organizer_id == current_user.id
    ).all()

    return events


from datetime import datetime, timedelta, timezone

@router.get("/{event_id}")
def get_full_event_details(
    event_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    event = db.query(Event).options(
        joinedload(Event.shows).joinedload(EventShow.seat_layout).joinedload(SeatLayout.seats),
        joinedload(Event.shows).joinedload(EventShow.seat_layout).joinedload(SeatLayout.sections),
        joinedload(Event.shows).joinedload(EventShow.venue)
    ).filter(
        Event.id == event_id,
        Event.organizer_id == current_user.id
    ).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    now = datetime.now(timezone.utc)
    active_shows = [
        show for show in event.shows 
        if (show.start_time + timedelta(minutes=event.estimated_duration_minutes)) > now
    ]

    # Find if any show already has a layout to act as the template
    existing_layout = next((show.seat_layout for show in event.shows if show.seat_layout), None)

    return {
        "id": str(event.id),
        "title": event.title,
        "description": event.description,
        "base_price": float(event.base_price),
        "image_url": event.image_url,
        "is_active": event.is_active,
        "category": event.category,
        "estimated_duration_minutes": event.estimated_duration_minutes,
        "shows": active_shows,
        "existing_layout": existing_layout # Send the layout directly
    }


@router.post("/create", response_model=EventResponse)
def create_event(
    event_in: EventCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    if current_user.role != "organizer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organizers can create events"
        )

    event = Event(
        organizer_id=current_user.id,
        title=event_in.title,
        description=event_in.description,
        entry_type=event_in.entry_type,
        category=event_in.category,
        estimated_duration_minutes=event_in.estimated_duration_minutes,
        base_price=event_in.base_price,
        image_url=event_in.image_url,
        is_active=True
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    return event


@router.post("/create-show", response_model=List[EventShowResponse])
def create_event_show(
    data: EventShowCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    event = db.query(Event).filter(Event.id == data.event_id).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.organizer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )

    venue = Venue(
        organizer_id=current_user.id,
        name=data.venue.name,
        formatted_address=data.venue.formatted_address,
        latitude=data.venue.latitude,
        longitude=data.venue.longitude
    )

    db.add(venue)
    db.commit()
    db.refresh(venue)

    created_shows = []

    duration = timedelta(minutes=event.estimated_duration_minutes)

    for start_time in data.start_times:

        end_time = start_time + duration

        show = EventShow(
            event_id=event.id,
            venue_id=venue.id,
            start_time=start_time,
            end_time=end_time,
            capacity=data.capacity
        )

        db.add(show)
        created_shows.append(show)

    db.commit()

    for show in created_shows:
        db.refresh(show)

    return created_shows



@router.post("/{event_id}/reviews")
def add_event_review(
    event_id: UUID,
    review_data: ReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    now = datetime.now(timezone.utc)

    booking = db.query(Booking).join(EventShow).filter(
        Booking.user_id == current_user.id,
        EventShow.event_id == event_id,
        Booking.status == SeatBookingStatus.BOOKED,
        Booking.is_checked_in == True,
        EventShow.start_time < now
    ).first()

    if not booking:
        raise HTTPException(
            status_code=403, 
            detail="You can only review events you have attended and checked into."
        )

    existing_review = db.query(Review).filter(
        Review.event_id == event_id,
        Review.user_id == current_user.id
    ).first()

    if existing_review:
        raise HTTPException(status_code=400, detail="You have already reviewed this event.")

    new_review = Review(
        event_id=event_id,
        user_id=current_user.id,
        rating=review_data.rating,
        comment=review_data.comment
    )

    db.add(new_review)
    db.commit()
    db.refresh(new_review)

    return {"status": "success", "message": "Review added successfully"}

@router.get("/pending-reviews")
def get_pending_reviews(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    now = datetime.now(timezone.utc)
    
    # Subquery to find events the user has already reviewed
    reviewed_events = db.query(Review.event_id).filter(Review.user_id == current_user.id).subquery()

    # Query for bookings where user checked in, event has passed, and user has NOT reviewed the event yet
    pending = db.query(Event).join(EventShow).join(Booking).filter(
        Booking.user_id == current_user.id,
        Booking.status == SeatBookingStatus.BOOKED,
        Booking.is_checked_in == True,
        EventShow.start_time < now,
        ~Event.id.in_(reviewed_events)
    ).distinct().all()

    return [
        {
            "event_id": str(event.id),
            "title": event.title,
            "image_url": event.image_url
        } for event in pending
    ]

@router.put("/{event_id}/reviews/{review_id}")
def update_event_review(
    event_id: UUID,
    review_id: UUID,
    review_data: ReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    review = db.query(Review).filter(
        Review.id == review_id,
        Review.event_id == event_id,
        Review.user_id == current_user.id
    ).first()
    
    if not review:
        raise HTTPException(status_code=404, detail="Review not found or you don't have permission to edit it.")

    review.rating = review_data.rating
    review.comment = review_data.comment
    db.commit()
    db.refresh(review)
    return {"status": "success", "message": "Review updated successfully"}

@router.delete("/{event_id}/reviews/{review_id}")
def delete_event_review(
    event_id: UUID,
    review_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    review = db.query(Review).filter(
        Review.id == review_id,
        Review.event_id == event_id,
        Review.user_id == current_user.id
    ).first()
    
    if not review:
        raise HTTPException(status_code=404, detail="Review not found or you don't have permission to delete it.")

    db.delete(review)
    db.commit()
    return {"status": "success", "message": "Review deleted successfully"}