from pydantic import BaseModel, EmailStr
from typing import Optional

class UserRegister(BaseModel):
    name: str
    email: EmailStr
    phone_number: str
    password: str

class VerifyOtpRequest(BaseModel):
    phone_number: str
    otp: str

class ResendOtpRequest(BaseModel):
    phone_number: str
 


class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str

    class Config:
        from_attributes = True


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UpdateProfileSchema(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None    