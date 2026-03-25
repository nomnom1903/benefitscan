"""
app/database.py — Database connection and session management

Why a dedicated database file (not in config.py or main.py):
The SQLAlchemy engine and session factory need to be importable from multiple
places (routes, tests) without creating circular imports. This file is the
single source of truth for the database connection.

SQLAlchemy concepts used here:
  Engine  — the connection to the database file itself
  Session — a "unit of work": reads/writes within a single request
  get_db  — FastAPI dependency that provides a session per request, then closes it

V2 migration path:
  Change settings.database_url to a PostgreSQL URL.
  Add pool_size and max_overflow to create_engine().
  Everything else stays the same.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.config import settings
from app.models.sbc import Base

# --- Create the database engine ---
# connect_args={"check_same_thread": False} is required for SQLite only —
# FastAPI may call the same connection from multiple threads.
# Remove this line when migrating to PostgreSQL.
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # SQLite-specific, remove for PostgreSQL
    echo=settings.is_development,               # Log SQL queries in development mode
)

# --- Create the session factory ---
# Each call to SessionLocal() produces a new database session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """
    Create all database tables if they don't exist yet.
    Called once at application startup.
    """
    Base.metadata.create_all(bind=engine)


def get_db():
    """
    FastAPI dependency that provides a database session for a single request.

    Usage in a route:
        @router.get("/example")
        def my_route(db: Session = Depends(get_db)):
            ...

    The `try/finally` ensures the session is always closed after the request,
    even if an exception is raised — preventing connection leaks.
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
