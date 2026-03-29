from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Enum, Boolean, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database.base import Base
from sqlalchemy.dialects.postgresql import UUID
import uuid
import enum

class OrganizerStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    permanently_rejected = "permanently_rejected"

class OrganizerApplication(Base):
    __tablename__ = "organizer_applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)
    
    organization_name = Column(String(255), nullable=False)
    address = Column(Text, nullable=False)
    contact_name = Column(String(255), nullable=False)
    contact_email = Column(String(255), nullable=False)
    contact_phone = Column(String(20), nullable=False)

    beneficiary_name = Column(String(255), nullable=False)
    account_type = Column(String(50), nullable=False) 
    bank_name = Column(String(255), nullable=False)
    account_number = Column(String(50), nullable=False)
    ifsc_code = Column(String(20), nullable=False)

    status = Column(Enum(OrganizerStatus), default=OrganizerStatus.pending)
    is_verified = Column(Boolean, default=False)
    
    rejection_count = Column(Integer, default=0)
    current_rejection_reason = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", backref="organizer_application")
    history = relationship("OrganizerApplicationHistory", back_populates="application", cascade="all, delete-orphan")

class OrganizerApplicationHistory(Base):
    __tablename__ = "organizer_application_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("organizer_applications.id"), nullable=False)
    
    rejection_reason = Column(Text, nullable=False)
    snapshot_data = Column(JSON, nullable=True)
    rejected_at = Column(DateTime(timezone=True), server_default=func.now())

    application = relationship("OrganizerApplication", back_populates="history")