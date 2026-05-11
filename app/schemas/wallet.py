from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import List, Optional

class WalletTransactionResponse(BaseModel):
    id: UUID
    amount: float
    tx_type: str
    description: Optional[str]
    created_at: datetime
    sender_wallet_id: Optional[UUID]
    receiver_wallet_id: Optional[UUID]

    class Config:
        from_attributes = True

class WalletDetailsResponse(BaseModel):
    id: UUID
    user_id: UUID
    balance: float
    transactions: List[WalletTransactionResponse]

    class Config:
        from_attributes = True

        