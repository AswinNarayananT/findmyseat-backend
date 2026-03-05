# app/models/__init__.py

# Import the Base
from app.database.base import Base

# Now import all models so they attach to that Base
from app.models.user import User
from app.models.otp import OTP
from app.models.organizer_application import OrganizerApplication
from app.models.password_reset import PasswordResetToken
from app.models.event import Event
from app.models.event_show import EventShow
from app.models.venue import Venue

# Explicitly export them
__all__ = [
    "Base",
    "User",
    "OTP",
    "OrganizerApplication",
    "PasswordResetToken",
    "Event",
    "EventShow",
    "Venue",
]