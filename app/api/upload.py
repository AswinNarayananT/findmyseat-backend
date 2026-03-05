from fastapi import APIRouter, Depends, HTTPException
from app.services.cloudinary_service import generate_signed_upload_params
from app.core.security import get_current_user

router = APIRouter(prefix="/upload", tags=["Upload"])

@router.get("/cloudinary-signature")
def get_cloudinary_signature(current_user=Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="User not authenticated")

    return generate_signed_upload_params()