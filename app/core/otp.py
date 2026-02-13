import random
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def generate_otp():
    return str(random.randint(100000, 999999))

def hash_otp(otp: str):
    return pwd_context.hash(otp)

def verify_otp(plain: str, hashed: str):
    return pwd_context.verify(plain, hashed)
