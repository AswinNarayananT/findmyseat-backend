from fastapi import APIRouter, Depends, HTTPException, Response, Header
from sqlalchemy.orm import Session
from app.database.session import SessionLocal
from app.models.user import User
from app.schemas.user import UserRegister, UserLogin, VerifyOtpRequest, ResendOtpRequest, ChangePasswordRequest
from datetime import datetime, timezone, timedelta
from app.models.otp import OTP
from app.core.otp import generate_otp, hash_otp
from app.services.sms_service import send_sms
from app.services.email import send_otp_email, resend_otp_email
from fastapi.security import OAuth2PasswordBearer
from app.core.config import settings
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_access_token
)

router = APIRouter(prefix="/admin", tags=["adminAuth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/admin/login")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



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
