from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.event import Event
from app.schemas.event import EventCreate, EventResponse
from app.database.dependencies import get_db
from app.core.security import get_current_user


router = APIRouter(prefix="/events", tags=["Events"])


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