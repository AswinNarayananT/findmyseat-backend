import uuid
import enum
from datetime import datetime
from sqlalchemy import (
    String,
    Text,
    DateTime,
    Enum,
    ForeignKey,
    Boolean,
    Numeric,
    Integer
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column, validates
from sqlalchemy.sql import func
from app.database.base import Base



class EntryType(str, enum.Enum):
    GENERAL = "general"
    SEAT_WISE = "seat_wise"


class EventCategory(str, enum.Enum):
    CONCERT = "concert"
    STANDUP = "standup"
    WORKSHOP = "workshop"
    EXPO = "expo"
    OTHER = "other"


class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    organizer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    entry_type: Mapped[EntryType] = mapped_column(
        Enum(EntryType, name="entry_type_enum"),
        nullable=False
    )

    category: Mapped[EventCategory] = mapped_column(
        Enum(EventCategory, name="event_category_enum"),
        nullable=False,
        default=EventCategory.OTHER
    )

    estimated_duration_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    base_price: Mapped[float] = mapped_column(
        Numeric(10, 2),
        nullable=False
    )

    image_url: Mapped[str | None] = mapped_column(String(500))
    image_public_id: Mapped[str | None] = mapped_column(String(255))
    image_version: Mapped[str | None] = mapped_column(String(50))

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )

    organizer = relationship("User", backref="events")

    shows = relationship(
        "EventShow",
        back_populates="event",
        cascade="all, delete-orphan"
    )
    reviews = relationship(
        "Review",
        back_populates="event",
        cascade="all, delete-orphan",
        order_by="Review.created_at.desc()"
    )
    is_cancelled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false"
    )


    @validates("base_price")
    def validate_price(self, key, value):
        if value is None or value <= 0:
            raise ValueError("Base price must be greater than 0")
        return value

    @validates("estimated_duration_minutes")
    def validate_duration(self, key, value):
        if value <= 0:
            raise ValueError("Duration must be greater than 0")
        return value
    
    @property
    def average_rating(self):
        if not self.reviews:
            return 0
        return sum(r.rating for r in self.reviews) / len(self.reviews)



class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    rating: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    comment: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    is_cancelled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    cancellation_reason: Mapped[str | None] = mapped_column(Text)

    event = relationship("Event", back_populates="reviews")
    user = relationship("User", backref="reviews")

    @validates("rating")
    def validate_rating(self, key, value):
        if not (1 <= value <= 5):
            raise ValueError("Rating must be between 1 and 5")
        return value