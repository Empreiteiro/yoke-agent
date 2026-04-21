from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.core.config import settings


def _build_engine(database_url: str):
    """Create an engine tuned for the backing database.

    SQLite needs ``check_same_thread=False`` so FastAPI's threadpool can share
    connections. Server-side databases (Postgres, MySQL…) benefit from
    ``pool_pre_ping`` to survive idle-connection drops.
    """
    url = make_url(database_url)
    if url.get_backend_name() == "sqlite":
        return create_engine(database_url, connect_args={"check_same_thread": False})
    return create_engine(database_url, pool_pre_ping=True)


engine = _build_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
