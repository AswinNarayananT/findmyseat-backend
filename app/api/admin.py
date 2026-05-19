from fastapi import APIRouter, Depends, HTTPException, Response, Header, status
from sqlalchemy.orm import Session
from app.database.dependencies import get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from typing import Optional
from sqlalchemy import func, extract
from app.database.dependencies import get_db
from app.models import Event, EventShow, Wallet
from app.models.event import Review
from app.models.seat import Booking
from app.models.finance import Wallet
from app.models.user import User, UserRole
from app.schemas.admin import AdminFinanceResponse
from app.models.organizer_application import OrganizerApplication, OrganizerStatus, OrganizerApplicationHistory
from app.models.finance import Wallet, Transaction, TransactionType, RedeemRequest, RedeemStatus
from datetime import datetime, timezone
from app.core.security import get_current_user
from app.schemas.user import UserLogin
from app.schemas.organizer_application import OrganizerApplicationResponse, OrganizerStatusUpdate
from fastapi.security import OAuth2PasswordBearer
from app.core.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
)
from uuid import UUID
from sqlalchemy.orm import Session, joinedload
from app.core.notifications import manager
from sqlalchemy import or_

router = APIRouter(prefix="/admin", tags=["adminAuth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/admin/login")


def get_admin_user(
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


@router.get("/me")
def get_admin_me(admin_user: User = Depends(get_admin_user)):
    return {
        "id": str(admin_user.id),
        "name": admin_user.name,
        "email": admin_user.email,
        "role": admin_user.role,
    }

@router.post("/login")
def admin_login(
    payload: UserLogin,
    response: Response,
    db: Session = Depends(get_db),
):

    user = db.query(User).filter(User.email == payload.email).first()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(payload.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized as admin")

    if user.is_blocked:
        raise HTTPException(status_code=403, detail="Admin account is blocked")

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False, 
        samesite="lax",
    )

    return {
        "message": "Admin login successful",
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
        },
    }


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        samesite="lax",
        secure=False,
    )
    return {"message": "Logged out successfully"}



@router.get(
    "/organizer-applications",
    response_model=list[OrganizerApplicationResponse],
)
def list_organizer_applications(
    status_filter: OrganizerStatus | None = None,
    search: str | None = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    query = db.query(OrganizerApplication)

    if status_filter:
        query = query.filter(OrganizerApplication.status == status_filter)

    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                OrganizerApplication.organization_name.ilike(search_filter),
                OrganizerApplication.contact_name.ilike(search_filter)
            )
        )

    applications = (
        query.order_by(OrganizerApplication.updated_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return applications




@router.get(
    "/organizer-applications/{application_id}",
    response_model=OrganizerApplicationResponse,
)
def get_organizer_application_detail(
    application_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    application = (
        db.query(OrganizerApplication)
        .options(joinedload(OrganizerApplication.history))
        .filter(OrganizerApplication.id == application_id)
        .first()
    )

    if not application:
        raise HTTPException(
            status_code=404,
            detail="Application not found"
        )

    return application


@router.patch(
    "/organizer-applications/{application_id}",
    response_model=OrganizerApplicationResponse
)
async def update_organizer_application_status(
    application_id: UUID,
    payload: OrganizerStatusUpdate,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    application = (
        db.query(OrganizerApplication)
        .filter(OrganizerApplication.id == application_id)
        .first()
    )

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    if application.status != OrganizerStatus.pending:
        raise HTTPException(
            status_code=400,
            detail="Only pending applications can be updated"
        )

    if payload.status == OrganizerStatus.rejected:
        if not payload.rejection_reason:
            raise HTTPException(
                status_code=400,
                detail="Rejection reason is required"
            )

        snapshot = {
            "organization_name": application.organization_name,
            "address": application.address,
            "contact_name": application.contact_name,
            "contact_email": application.contact_email,
            "contact_phone": application.contact_phone,
            "beneficiary_name": application.beneficiary_name,
            "account_type": application.account_type,
            "bank_name": application.bank_name,
            "account_number": application.account_number,
            "ifsc_code": application.ifsc_code
        }

        history_entry = OrganizerApplicationHistory(
            application_id=application.id,
            rejection_reason=payload.rejection_reason,
            snapshot_data=snapshot
        )
        db.add(history_entry)

        application.rejection_count += 1
        application.current_rejection_reason = payload.rejection_reason
        
        if application.rejection_count >= 3:
            application.status = OrganizerStatus.permanently_rejected
        else:
            application.status = OrganizerStatus.rejected

    elif payload.status == OrganizerStatus.approved:
        application.status = OrganizerStatus.approved
        application.is_verified = True
        application.current_rejection_reason = None

        user = db.query(User).filter(User.id == application.user_id).first()
        if user:
            user.role = "organizer"
            
        await manager.send_personal_message({
            "type": "APPLICATION_ACCEPTED",
            "title": "Application Approved",
            "message": "Your organizer application has been approved!"
        }, str(application.user_id))

    db.commit()
    db.refresh(application)

    return application



@router.get("/finance/global-summary", response_model=AdminFinanceResponse)
def get_admin_finance_dashboard(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    organizer_id: Optional[UUID] = None,
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2024),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")

    query = db.query(EventShow).join(Event).join(User, Event.organizer_id == User.id)

    if organizer_id:
        query = query.filter(Event.organizer_id == organizer_id)
    if month:
        query = query.filter(extract('month', EventShow.start_time) == month)
    if year:
        query = query.filter(extract('year', EventShow.start_time) == year)

    total_stats = db.query(
        func.sum(EventShow.total_revenue_collected).label("gross"),
        func.sum(EventShow.booked_count).label("tickets"),
        func.count(Event.id.distinct()).label("events")
    ).first()

    monthly_query = db.query(
        func.to_char(EventShow.start_time, 'Month YYYY').label("month_year"),
        func.sum(EventShow.total_revenue_collected).label("monthly_gross"),
        func.count(EventShow.id).label("monthly_shows")
    ).group_by("month_year").all()

    total_count = query.count()
    total_pages = (total_count + limit - 1) // limit
    shows_data = query.order_by(EventShow.start_time.desc()).offset((page - 1) * limit).limit(limit).all()

    return {
        "summary": {
            "total_platform_gross": float(total_stats.gross or 0),
            "total_admin_commission": float(total_stats.gross or 0) * 0.10,
            "total_organizer_payouts": float(total_stats.gross or 0) * 0.90,
            "active_events_count": total_stats.events or 0,
            "total_tickets_sold": total_stats.tickets or 0
        },
        "monthly_breakdown": [
            {
                "month": m.month_year.strip(),
                "gross_revenue": float(m.monthly_gross or 0),
                "commission": float(m.monthly_gross or 0) * 0.10,
                "show_count": m.monthly_shows
            } for m in monthly_query
        ],
        "shows": [
            {
                "show_id": s.id,
                "event_title": s.event.title,
                "organizer_name": s.event.organizer.name,
                "start_time": s.start_time,
                "status": "cancelled" if s.is_cancelled else "active",
                "tickets_sold": s.booked_count,
                "gross_revenue": float(s.total_revenue_collected),
                "admin_commission": float(s.total_revenue_collected) * 0.10,
                "organizer_share": float(s.total_revenue_collected) * 0.90,
                "is_payout_processed": s.is_payout_processed
            } for s in shows_data
        ],
        "total_pages": total_pages,
        "current_page": page
    }

@router.get("/redeem-requests")
def get_redeem_requests(
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    requests = db.query(RedeemRequest).options(
        joinedload(RedeemRequest.event).joinedload(Event.reviews).joinedload(Review.user),
        joinedload(RedeemRequest.organizer)
    ).order_by(RedeemRequest.created_at.desc()).all()

    for req in requests:
        if req.event and req.event.reviews:
            for review in req.event.reviews:
                review.user_name = review.user.name if review.user else "Anonymous"
    
    return requests

@router.post("/redeem-requests/{request_id}/process")
async def process_redeem_request(
    request_id: UUID,
    status: str, 
    admin_notes: Optional[str] = None,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    req = db.query(RedeemRequest).options(
        joinedload(RedeemRequest.event),
        joinedload(RedeemRequest.organizer)
    ).filter(RedeemRequest.id == request_id).first()

    if not req:
        raise HTTPException(status_code=404, detail="Redeem request not found")

    if req.status != RedeemStatus.PENDING:
        raise HTTPException(status_code=400, detail="Request already processed")

    if status == "approved":
        admin_wallet = db.query(Wallet).filter(Wallet.user_id == admin_user.id).first()
        organizer_wallet = db.query(Wallet).filter(Wallet.user_id == req.organizer_id).first()

        if not admin_wallet or float(admin_wallet.balance) < float(req.payable_amount):
            raise HTTPException(status_code=400, detail="Insufficient platform balance for payout")
        
        if not organizer_wallet:
            organizer_wallet = Wallet(user_id=req.organizer_id, balance=0.0)
            db.add(organizer_wallet)
            db.flush()

        admin_wallet.balance = float(admin_wallet.balance) - float(req.payable_amount)
        organizer_wallet.balance = float(organizer_wallet.balance) + float(req.payable_amount)

        db.add(Transaction(
            sender_wallet_id=admin_wallet.id,
            receiver_wallet_id=organizer_wallet.id,
            amount=req.payable_amount,
            tx_type=TransactionType.PAYOUT,
            description=f"Approved Payout for Event: {req.event.title}. Total: {req.total_amount}, Fee (10%): {req.commission_amount}"
        ))

        req.status = RedeemStatus.APPROVED
        
        await manager.send_personal_message({
            "type": "PAYOUT_APPROVED",
            "title": "Payout Approved!",
            "message": f"Your payout for {req.event.title} has been approved. ₹{req.payable_amount} added to your wallet."
        }, str(req.organizer_id))

    else:
        req.status = RedeemStatus.REJECTED
        
        await manager.send_personal_message({
            "type": "PAYOUT_REJECTED",
            "title": "Payout Rejected",
            "message": f"Your payout for {req.event.title} was rejected. Reason: {admin_notes or 'No reason provided.'}"
        }, str(req.organizer_id))

    req.admin_notes = admin_notes
    req.processed_at = datetime.now(timezone.utc)
    db.commit()

    return {"status": "success", "message": f"Request {status} successfully"}

@router.get("/users")
def list_users(
    role: Optional[str] = None,
    is_blocked: Optional[bool] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    if is_blocked is not None:
        query = query.filter(User.is_blocked == is_blocked)
    if search:
        query = query.filter(
            (User.name.ilike(f"%{search}%")) | (User.email.ilike(f"%{search}%"))
        )
    
    total = query.count()
    users = query.order_by(User.created_at.desc()).offset((page-1)*limit).limit(limit).all()
    
    return {
        "users": users,
        "total": total,
        "page": page,
        "total_pages": (total + limit - 1) // limit
    }

@router.post("/users/{user_id}/toggle-block")
def toggle_user_block(
    user_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot block yourself")
        
    user.is_blocked = not user.is_blocked
    db.commit()
    return {"status": "success", "is_blocked": user.is_blocked}

@router.get("/events-list")
def list_all_events(
    category: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    query = db.query(Event).options(joinedload(Event.organizer))
    if category:
        query = query.filter(Event.category == category)
    if is_active is not None:
        query = query.filter(Event.is_active == is_active)
    if search:
        query = query.filter(Event.title.ilike(f"%{search}%"))
        
    total = query.count()
    events = query.order_by(Event.created_at.desc()).offset((page-1)*limit).limit(limit).all()
    
    return {
        "events": [
            {
                "id": str(e.id),
                "title": e.title,
                "category": e.category,
                "is_active": e.is_active,
                "created_at": e.created_at,
                "organizer_name": e.organizer.name if e.organizer else "N/A",
                "organizer_email": e.organizer.email if e.organizer else "N/A"
            } for e in events
        ],
        "total": total,
        "page": page,
        "total_pages": (total + limit - 1) // limit
    }

