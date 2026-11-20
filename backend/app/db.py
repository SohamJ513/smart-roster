import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def normalize_url(url: str) -> str:
    """Hosts like Neon hand out `postgresql://...`; SQLAlchemy needs to be told to use the psycopg 3 driver."""
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def make_engine(url: str | None = None):
    url = normalize_url(url or os.environ.get("DATABASE_URL", "sqlite:///./roster.db"))
    kwargs = {}
    if url.startswith("postgresql"):
        # Neon suspends idle databases and drops their connections: test a connection before using it.
        kwargs.update(pool_pre_ping=True, pool_recycle=300)
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in url:
            from sqlalchemy.pool import StaticPool
            kwargs["poolclass"] = StaticPool
    eng = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        @event.listens_for(eng, "connect")
        def _fk_on(dbapi_conn, _record):  # SQLite ignores foreign keys unless asked
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
    return eng


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db(bind=None) -> None:
    from app import models  # noqa: F401  (register tables)
    Base.metadata.create_all(bind or engine)


def get_session():
    with SessionLocal() as session:
        yield session