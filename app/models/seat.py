import uuid
import enum
import string
from datetime import datetime
from sqlalchemy import Integer, String, Numeric, Enum, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from app.database.base import Base


class SeatType(str, enum.Enum):
    REGULAR = "regular"
    VIP = "vip"
    PREMIUM = "premium"
    EMPTY = "empty"


class SeatLayout(Base):
    __tablename__ = "seat_layouts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    venue_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=True)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    total_columns: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    blocks = relationship("SeatBlock", back_populates="layout", cascade="all, delete-orphan")
    seats = relationship("Seat", back_populates="layout", cascade="all, delete-orphan")
    shows = relationship("EventShow", back_populates="layout")


class SeatBlock(Base):
    __tablename__ = "seat_blocks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    layout_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=True)
    seat_type: Mapped[SeatType] = mapped_column(Enum(SeatType), nullable=False, default=SeatType.REGULAR)

    num_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    num_columns: Mapped[int] = mapped_column(Integer, nullable=False)

    start_row: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    start_column: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    layout = relationship("SeatLayout", back_populates="blocks")
    seats = relationship("Seat", back_populates="block", cascade="all, delete-orphan")


class Seat(Base):
    __tablename__ = "seats"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    layout_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    block_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    column_number: Mapped[int] = mapped_column(Integer, nullable=False)
    seat_number: Mapped[str] = mapped_column(String(10), nullable=True)
    seat_type: Mapped[SeatType] = mapped_column(Enum(SeatType), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(10,2), nullable=True)

    layout = relationship("SeatLayout", back_populates="seats")
    block = relationship("SeatBlock", back_populates="seats")
    bookings = relationship("BookingSeat", back_populates="seat")


def generate_seats(layout: SeatLayout):
    all_seats = []
    blocks = sorted(layout.blocks, key=lambda b: b.position)
    current_row_offset = 0

    for block in blocks:
        for r in range(block.num_rows):
            row_number = current_row_offset + r + 1
            row_letter = string.ascii_uppercase[row_number - 1]

            for c in range(1, block.num_columns + 1):
                if block.seat_type == SeatType.EMPTY:
                    seat = Seat(
                        layout_id=layout.id,
                        block_id=block.id,
                        row_number=row_number,
                        column_number=c,
                        seat_number=None,
                        seat_type=SeatType.EMPTY
                    )
                else:
                    seat_number = f"{row_letter}{c}"
                    seat = Seat(
                        layout_id=layout.id,
                        block_id=block.id,
                        row_number=row_number,
                        column_number=c,
                        seat_number=seat_number,
                        seat_type=block.seat_type
                    )
                all_seats.append(seat)
        current_row_offset += block.num_rows
    return all_seats