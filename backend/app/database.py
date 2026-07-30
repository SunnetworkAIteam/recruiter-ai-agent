"""
Database engine and session management.

WHY pool_pre_ping and conservative pool sizes:
Supabase (and most hosted Postgres) will silently close idle connections.
Without `pool_pre_ping=True`, your first request after any idle period
throws a cryptic `OperationalError: server closed the connection
unexpectedly` — this is one of the single most common production bugs
in FastAPI + hosted-Postgres stacks, and it's invisible in local dev
because your local Postgres never closes idle connections.

pool_size is deliberately small (5) because Koyeb/Render free-to-mid
tiers and Supabase's connection limits are shared resources — a pool
that's too large starves other services or hits Supabase's connection
cap under concurrent load.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=300,  # recycle connections every 5 min, well under most hosted timeouts
    echo=not settings.is_production,  # SQL query logging in dev only — never in prod (perf + log noise)
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency. Guarantees the session is closed even if the
    request handler raises — a leaked session under load is how you
    exhaust the connection pool and take down the whole API.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
