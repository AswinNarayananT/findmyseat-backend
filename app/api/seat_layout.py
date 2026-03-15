from fastapi import APIRouter, Depends, HTTPException
from app.database.dependencies import get_db
from sqlalchemy.orm import Session
from app.schemas.seat import SeatLayoutCreateSchema
from app.models.seat import SeatLayout, SeatSection, Seat, SeatType
from app.models.event_show import EventShow 
import uuid

router = APIRouter(prefix="/seat-layout", tags=["Seat Layout"])

@router.post("/bulk-create")
async def bulk_create_seat_layouts(
    payload: SeatLayoutCreateSchema, 
    db: Session = Depends(get_db)
):

    seat_type_map = {
        "seat": SeatType.SEAT,
        "aisle": SeatType.AISLE,
        "empty": SeatType.EMPTY
    }

    try:
        for show_id in payload.event_show_ids:
            existing = db.query(SeatLayout).filter(SeatLayout.event_show_id == show_id).first()
            if existing:
                db.delete(existing)
                db.flush()

            new_layout = SeatLayout(
                event_show_id=show_id,
                rows=payload.rows,
                columns=payload.columns
            )
            db.add(new_layout)
            db.flush()

            created_sections = []
            for sec_data in payload.sections:
                new_section = SeatSection(
                    layout_id=new_layout.id,
                    name=sec_data.name,
                    price=sec_data.price,
                    display_order=sec_data.display_order,
                    color=sec_data.color
                )
                db.add(new_section)
                created_sections.append(new_section)
            
            db.flush() 

            for seat_data in payload.seats:
                target_section_id = None

                if seat_data.seat_type == "seat" and seat_data.section_index is not None:
                    if 0 <= seat_data.section_index < len(created_sections):
                        target_section_id = created_sections[seat_data.section_index].id

                resolved_type = seat_type_map.get(seat_data.seat_type.lower())
                if not resolved_type:
                    continue

                new_seat = Seat(
                    layout_id=new_layout.id,
                    section_id=target_section_id,
                    row_label=seat_data.row_label,
                    seat_number=seat_data.seat_number,
                    x_position=seat_data.x_position,
                    y_position=seat_data.y_position,
                    seat_type=resolved_type
                )
                db.add(new_seat)

        db.commit()
        return {"status": "success", "message": f"Layout applied to {len(payload.event_show_ids)} shows."}

    except Exception as e:
        db.rollback()
        print(f"DATABASE ERROR: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Database error: {str(e)}")