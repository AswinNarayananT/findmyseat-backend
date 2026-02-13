from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from app.core.config import settings

conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_STARTTLS=settings.MAIL_STARTTLS,
    MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
    USE_CREDENTIALS=True,
)

async def send_otp_email(email: str, otp: str):
    message = MessageSchema(
        subject="Your FindMySeat OTP Code",
        recipients=[email],
        body=f"""
        Your FindMySeat OTP is: {otp}

        It expires in {settings.OTP_EXPIRE_MINUTES} minutes.

        If you did not request this, ignore this email.
        """,
        subtype="plain",
    )

    fm = FastMail(conf)
    await fm.send_message(message)


async def resend_otp_email(email: str, otp: str):
    """
    Send OTP to the user's email when they request a resend.
    """
    message = MessageSchema(
        subject="Your FindMySeat OTP - Resend",
        recipients=[email],
        body=f"""
        Your requested FindMySeat OTP is: {otp}

        It expires in {settings.OTP_EXPIRE_MINUTES} minutes.

        If you did not request this, please ignore this email.
        """,
        subtype="plain",
    )

    fm = FastMail(conf)
    await fm.send_message(message)
