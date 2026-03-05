from app.core.config import settings
import cloudinary
import cloudinary.uploader
import cloudinary.api

cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True
)

def generate_signed_upload_params(folder: str = "events", public_id: str = None):
    """
    Generate signed payload for frontend direct upload
    """
    timestamp = int(cloudinary.utils.now())
    params = {
        "folder": folder,
        "timestamp": timestamp,
    }
    if public_id:
        params["public_id"] = public_id

    signature = cloudinary.utils.api_sign_request(
        params, 
        settings.CLOUDINARY_API_SECRET
    )
    params["signature"] = signature
    params["api_key"] = settings.CLOUDINARY_API_KEY
    return params

def upload_file(file_path: str, folder: str = "events"):
    """
    Optional: Backend upload (slower, but possible)
    """
    result = cloudinary.uploader.upload(file_path, folder=folder)
    return {
        "public_id": result.get("public_id"),
        "url": result.get("secure_url"),
        "version": result.get("version")
    }