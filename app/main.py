from fastapi import FastAPI
import app.models
from app.api.auth import router as auth_router
from app.api.user import router as user_router
from app.api.admin import router as admin_router
from app.api.organizer import router as organizer_router
from app.api.password_reset import router as password_reset_router
from app.api.upload import router as upload_router
from app.api.event import router as event_router
from app.api.seat_layout import router as seat_layout_router
from app.api.notifications import router as notification_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Find My Seat API")

app.include_router(auth_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(organizer_router, prefix="/api/v1")
app.include_router(password_reset_router,prefix="/api/v1")
app.include_router(event_router,prefix="/api/v1")
app.include_router(upload_router, prefix="/api/v1")
app.include_router(seat_layout_router,prefix="/api/v1")
app.include_router(user_router,prefix="/api/v1")
app.include_router(notification_router,prefix="/api/v1")


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health_check():
    return {"status": "Backend running 🚀"}
