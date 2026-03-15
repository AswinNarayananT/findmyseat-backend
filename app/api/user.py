from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from app.database.dependencies import get_db
from sqlalchemy.orm import Session, joinedload
from uuid import UUID
from app.models.event import Event
from app.models.event_show import EventShow
from app.models.seat import SeatLayout
from typing import List

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
        joinedload(EventShow.seat_layout).joinedload(SeatLayout.sections),
        joinedload(EventShow.seat_layout).joinedload(SeatLayout.seats),
        joinedload(EventShow.venue)
    ).filter(EventShow.id == show_id).first()

    if not show:
        raise HTTPException(status_code=404, detail="Show not found")

    other_shows = db.query(EventShow).filter(
        EventShow.event_id == show.event_id,
    ).order_by(EventShow.start_time).all()

    return {
        "current_show": show,
        "other_shows": other_shows
    }