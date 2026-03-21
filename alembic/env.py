import sys
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# -----------------------------
# Add project root to sys.path
# -----------------------------
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# -----------------------------
# Import app settings & models
# -----------------------------
from app.core.config import settings
from app.database.base import Base

# IMPORTANT: Import all models here so Alembic detects them
from app.models.user import User  
from app.models.otp import OTP
from app.models.organizer_application import OrganizerApplication
from app.models.password_reset import PasswordResetToken
from app.models.event import Event
from app.models.event_show import EventShow
from app.models.venue import Venue
from app.models.seat import SeatLayout, SeatSection, Seat, SeatBooking
from app.models.finance import Wallet, Payment, Transaction


# -----------------------------
# Alembic Config
# -----------------------------
config = context.config

# Override DB URL using .env
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Setup logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata for autogenerate
target_metadata = Base.metadata


# -----------------------------
# OFFLINE MODE
# -----------------------------
def run_migrations_offline() -> None:
    """Run migrations in offline mode."""

    url = settings.DATABASE_URL

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,  # Detect column type changes
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# -----------------------------
# ONLINE MODE
# -----------------------------
def run_migrations_online() -> None:
    """Run migrations in online mode."""

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # Detect enum / column changes
        )

        with context.begin_transaction():
            context.run_migrations()


# -----------------------------
# Run Mode Switch
# -----------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
