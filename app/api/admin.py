from fastapi import APIRouter, Depends, HTTPException, Response, Header, status
from sqlalchemy.orm import Session
from app.database.dependencies import get_db
from app.models.user import User
from app.models.organizer_application import OrganizerApplication, OrganizerStatus, OrganizerApplicationHistory
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


from sqlalchemy import or_

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
def update_organizer_application_status(
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

    db.commit()
    db.refresh(application)

    return application