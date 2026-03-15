from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from datetime import timedelta
from typing import List
from uuid import UUID

from app.database.dependencies import get_db
from app.core.security import get_current_user
from app.models.event import Event
from app.models.event_show import EventShow
from app.models.venue import Venue
from app.schemas.event import EventCreate, EventResponse
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


@router.get("/{event_id}")
def get_full_event_details(
    event_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    event = db.query(Event).options(
        joinedload(Event.shows).joinedload(EventShow.seat_layout)
    ).filter(
        Event.id == event_id,
        Event.organizer_id == current_user.id
    ).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return event


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