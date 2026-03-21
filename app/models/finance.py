import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Numeric, ForeignKey, DateTime, Enum, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

class TransactionType(enum.Enum):
    BOOKING = "booking"
    REFUND = "refund"
    PAYOUT = "payout" 
    TOPUP = "topup"    

class PaymentStatus(enum.Enum):
    PENDING = "pending"
    CAPTURED = "captured"
    FAILED = "failed"
    REFUNDED = "refunded"

class Wallet(Base):

    __tablename__ = "wallets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True)
    balance: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)

    user = relationship("User", back_populates="wallet")

    sent_transactions = relationship(
        "Transaction", 
        foreign_keys="[Transaction.sender_wallet_id]", 
        back_populates="sender_wallet"
    )
    received_transactions = relationship(
        "Transaction", 
        foreign_keys="[Transaction.receiver_wallet_id]", 
        back_populates="receiver_wallet"
    )

class Payment(Base):

    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    razorpay_order_id: Mapped[str] = mapped_column(String(100), unique=True)
    razorpay_payment_id: Mapped[str | None] = mapped_column(String(100))
    razorpay_signature: Mapped[str | None] = mapped_column(String(200))
    
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Transaction(Base):

    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    payment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("payments.id"))
    booking_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("seat_bookings.id"))

    sender_wallet_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("wallets.id"))
    receiver_wallet_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("wallets.id"))
    
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    tx_type: Mapped[TransactionType] = mapped_column(Enum(TransactionType))
    description: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sender_wallet = relationship("Wallet", foreign_keys=[sender_wallet_id], back_populates="sent_transactions")
    receiver_wallet = relationship("Wallet", foreign_keys=[receiver_wallet_id], back_populates="received_transactions")