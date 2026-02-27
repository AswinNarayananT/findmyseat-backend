from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.dependencies import get_db
from app.models.user import User
from app.models.password_reset import PasswordResetToken
from app.schemas.password_reset import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from app.utils.reset_token import generate_reset_token, hash_token
from app.core.security import hash_password
from app.services.email import send_password_reset_email
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["Password Reset"])


@router.post("/forgot-password")
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == payload.email).first()

    if not user:
        return {"message": "The email does not exits"}

    raw_token = generate_reset_token()
    token_hash = hash_token(raw_token)

    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )

    db.add(reset_token)
    db.commit()

    reset_url = (
        f"{settings.FRONTEND_BASE_URL}"
        f"{settings.FRONTEND_RESET_PASSWORD_PATH}"
        f"?token={raw_token}"
    )

    await send_password_reset_email(
        email=user.email,
        reset_url=reset_url
    )

    return {"message": "A reset link has been sent to your email."}


@router.post("/reset-password")
async def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    token_hash = hash_token(payload.token)

    token_record = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.is_used == False,
            PasswordResetToken.expires_at > datetime.now(timezone.utc),
        )
        .first()
    )

    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token",
        )

    user = db.query(User).filter(User.id == token_record.user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token",
        )

    user.password = hash_password(payload.new_password)
    token_record.is_used = True

    db.commit()

    return {"message": "Password successfully reset"}