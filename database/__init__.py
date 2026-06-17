"""
CassanovaL SQLite database layer.
Single file: data/cassanoval.db  (no external server needed)
"""
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

_DB_PATH = "data/cassanoval.db"
_engine = create_engine(
    f"sqlite:///{_DB_PATH}",
    connect_args={"check_same_thread": False},
)
_SessionLocal = sessionmaker(bind=_engine, autoflush=True, autocommit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Create all tables if they do not exist. Safe to call on every startup."""
    from database import models  # noqa: F401 — registers ORM classes
    Base.metadata.create_all(_engine)


@contextmanager
def get_session():
    """Context manager that yields a Session and commits/rolls back on exit."""
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
