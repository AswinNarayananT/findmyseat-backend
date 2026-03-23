import uuid
import enum
from datetime import datetime, timedelta

from sqlalchemy import Integer, String, Numeric, Enum, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

from app.database.base import Base


class SeatType(enum.Enum):
    SEAT = "seat"
    AISLE = "aisle"
    EMPTY = "empty"


class SeatLayout(Base):
    __tablename__ = "seat_layouts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    event_show_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("event_shows.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )

    rows: Mapped[int] = mapped_column(Integer, nullable=False)
    columns: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    event_show = relationship("EventShow", back_populates="seat_layout")

    sections = relationship("SeatSection", back_populates="layout", cascade="all, delete-orphan")

    seats = relationship("Seat", back_populates="layout", cascade="all, delete-orphan")


class SeatSection(Base):
    __tablename__ = "seat_sections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    layout_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("seat_layouts.id", ondelete="CASCADE"),
        nullable=False
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)

    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    display_order: Mapped[int] = mapped_column(Integer, nullable=False)

    color: Mapped[str | None] = mapped_column(String(20))

    layout = relationship("SeatLayout", back_populates="sections")

    seats = relationship("Seat", back_populates="section", cascade="all, delete-orphan")


class Seat(Base):
    __tablename__ = "seats"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    layout_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("seat_layouts.id", ondelete="CASCADE"),
        nullable=False
    )

    section_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("seat_sections.id", ondelete="SET NULL")
    )

    row_label: Mapped[str | None] = mapped_column(String(5))

    seat_number: Mapped[int | None] = mapped_column(Integer)

    x_position: Mapped[int] = mapped_column(Integer, nullable=False)

    y_position: Mapped[int] = mapped_column(Integer, nullable=False)

    seat_type: Mapped[SeatType] = mapped_column(Enum(SeatType, name="seat_type_enum"), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    layout = relationship("SeatLayout", back_populates="seats")

    section = relationship("SeatSection", back_populates="seats")

    seat_bookings = relationship("SeatBooking", back_populates="seat", cascade="all, delete-orphan")



class SeatBookingStatus(enum.Enum):
    LOCKED = "locked"
    BOOKED = "booked"
    CANCELLED = "cancelled"


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    event_show_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("event_shows.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    status: Mapped[SeatBookingStatus] = mapped_column(
        Enum(SeatBookingStatus, name="seat_booking_status_enum"),
        default=SeatBookingStatus.LOCKED,
        nullable=False
    )

    is_checked_in: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    booked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")
    event_show = relationship("EventShow")
    seat_bookings = relationship("SeatBooking", back_populates="booking", cascade="all, delete-orphan")


class SeatBooking(Base):
    __tablename__ = "seat_bookings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    seat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("seats.id", ondelete="CASCADE"),
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    booking = relationship("Booking", back_populates="seat_bookings")
    seat = relationship("Seat", back_populates="seat_bookings")  