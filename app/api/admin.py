from fastapi import APIRouter, Depends, HTTPException, Response, Header, status
from sqlalchemy.orm import Session
from app.database.dependencies import get_db
from app.models.user import User
from app.models.organizer_application import OrganizerApplication, OrganizerStatus
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


@router.get(
    "/organizer-applications",
    response_model=list[OrganizerApplicationResponse],
)
def list_organizer_applications(
    status_filter: OrganizerStatus  | None = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    query = db.query(OrganizerApplication)

    if status_filter:
        query = query.filter(
            OrganizerApplication.status == status_filter
        )

    applications = (
        query.order_by(OrganizerApplication.created_at.desc())
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
    application = db.query(OrganizerApplication).filter(
        OrganizerApplication.id == application_id
    ).first()

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

    if payload.status == OrganizerStatus.rejected and not payload.rejection_reason:
        raise HTTPException(
            status_code=400,
            detail="Rejection reason is required"
        )

    application.status = payload.status
    application.rejection_reason = payload.rejection_reason

    if payload.status == OrganizerStatus.approved:
        application.is_verified = True
        application.rejection_reason = None

        user = db.query(User).filter(User.id == application.user_id).first()
        if user:
            user.role = "organizer"

    db.commit()
    db.refresh(application)

    return application