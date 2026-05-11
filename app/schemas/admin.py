from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid

class AdminRevenueSummary(BaseModel):
    total_platform_gross: float
    total_admin_commission: float
    total_organizer_payouts: float
    active_events_count: int
    total_tickets_sold: int

class MonthlyStats(BaseModel):
    month: str # e.g., "March 2026"
    gross_revenue: float
    commission: float
    show_count: int

class AdminShowDetail(BaseModel):
    show_id: uuid.UUID
    event_title: str
    organizer_name: str
    start_time: datetime
    status: str
    tickets_sold: int
    gross_revenue: float
    admin_commission: float
    organizer_share: float
    is_payout_processed: bool

class AdminFinanceResponse(BaseModel):
    summary: AdminRevenueSummary
    monthly_breakdown: List[MonthlyStats]
    shows: List[AdminShowDetail]
    total_pages: int
    current_page: int