import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.database.base import Base


from sqlalchemy import Enum
import enum

class UserRole(str, enum.Enum):
    USER = "user"
    ORGANIZER = "organizer"
    ADMIN = "admin"



class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    name: Mapped[str] = mapped_column(String(100), nullable=False)

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)

    phone_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=True)

    password: Mapped[str] = mapped_column(String(255), nullable=True)

    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.USER)

    is_google_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    is_otp_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    last_logined:Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    wallet = relationship("Wallet", back_populates="user", uselist=False, cascade="all, delete-orphan")

