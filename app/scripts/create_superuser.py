from getpass import getpass
from sqlalchemy.orm import Session
from app.database.session import SessionLocal
from app.models.user import User
from app.core.security import hash_password


def create_superuser():
    db: Session = SessionLocal()

    try:
        print("=== Create Superuser ===")

        name = input("Name: ").strip()
        email = input("Email: ").strip()
        phone_number = input("Phone Number: ").strip()

        # Check if user already exists
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            print("❌ User with this email already exists")
            return

        # Password confirmation loop
        while True:
            password = getpass("Password: ")
            confirm_password = getpass("Confirm Password: ")

            if not password:
                print("❌ Password cannot be empty")
                continue

            if password != confirm_password:
                print("❌ Passwords do not match. Try again.\n")
                continue

            break

        user = User(
            name=name,
            email=email,
            phone_number=phone_number,
            password=hash_password(password),
            role="admin",
            is_active=True,
            is_otp_verified=True,
        )

        db.add(user)
        db.commit()

        print("✅ Superuser created successfully!")

    finally:
        db.close()


if __name__ == "__main__":
    create_superuser()
