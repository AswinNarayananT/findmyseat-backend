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

router = APIRouter(prefix="/auth", tags=["Auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



@router.post("/register")
async def register(user_data: UserRegister, db: Session = Depends(get_db)):

    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    if db.query(User).filter(User.phone_number == user_data.phone_number).first():
        raise HTTPException(status_code=400, detail="Phone number already registered")

    user = User(
        name=user_data.name,
        email=user_data.email,
        phone_number=user_data.phone_number,
        password=hash_password(user_data.password),
        is_otp_verified=False,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    otp_code = generate_otp()

    otp_record = OTP(
        phone_number=user.phone_number,
        otp_hash=hash_otp(otp_code),
        expires_at=datetime.now(timezone.utc)
        + timedelta(minutes=settings.OTP_EXPIRE_MINUTES),
    )

    db.add(otp_record)
    db.commit()

    await send_otp_email(user.email, otp_code)

    return {
        "message": "User registered successfully. OTP sent to email.",
        "user_id": str(user.id),
    }



@router.post("/verify-otp")
def verify_otp(
    data: VerifyOtpRequest,
    response: Response,
    db: Session = Depends(get_db),
):

    phone_number = data.phone_number
    otp = data.otp

    otp_record = (
        db.query(OTP)
        .filter(
            OTP.phone_number == phone_number,
            OTP.is_used == False
        )
        .order_by(OTP.expires_at.desc())
        .first()
    )

    if not otp_record:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    if otp_record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="OTP expired")

    from app.core.otp import verify_otp as verify_otp_hash

    if not verify_otp_hash(otp, otp_record.otp_hash):
        raise HTTPException(status_code=400, detail="Incorrect OTP")

    otp_record.is_used = True

    user = db.query(User).filter(User.phone_number == phone_number).first()
    user.is_otp_verified = True

    db.commit()

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
        "access_token": access_token,
        "token_type": "Bearer",
        "user": {
            "id": str(user.id),
            "name": user.name,
            "phone_number":user.phone_number,
            "email": user.email,
            "role": user.role,
        },
    }


@router.post("/resend-otp")
async def resend_otp(
    data: ResendOtpRequest,
    db: Session = Depends(get_db),
):
    phone_number = data.phone_number

    user = db.query(User).filter(User.phone_number == phone_number).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_otp_verified:
        raise HTTPException(status_code=400, detail="User already verified")

    db.query(OTP).filter(
        OTP.phone_number == phone_number,
        OTP.is_used == False
    ).update({"is_used": True}, synchronize_session=False)

    otp_code = generate_otp()
    otp_hash = hash_otp(otp_code)

    new_otp = OTP(
        phone_number=phone_number,
        otp_hash=otp_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        is_used=False,
    )

    db.add(new_otp)
    db.commit()

    await resend_otp_email(user.email, otp_code)

    return {
        "message": "OTP resent successfully",
        "phone_number": phone_number,
        "expires_in": 120, 
    }

@router.post("/login")
def login(user_data: UserLogin, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_data.email).first()
    if not user or not verify_password(user_data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

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
        "access_token": access_token,
        "token_type": "Bearer",
        "user": {
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
            "phone_number":user.phone_number,
            "role": user.role,
        },
    }


@router.post("/change-password")
def change_password(
    data: ChangePasswordRequest,
    authorization: str = Header(...),
    db: Session = Depends(get_db),
):
    try:
        token = authorization.split(" ")[1]
    except IndexError:  
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    payload = decode_access_token(token)

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload.get("sub")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(data.current_password, user.password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    user.password = hash_password(data.new_password)

    db.commit()

    return {"message": "Password changed successfully"}