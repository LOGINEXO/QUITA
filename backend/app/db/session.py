from __future__ import annotations

import os
from functools import lru_cache
from typing import Generator

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker


def normalize_database_url(url: str) -> str:
    """Normalize URLs commonly supplied by managed PostgreSQL providers."""
    if url.startswith("postgres://"):
        return "postgresql://" + url.removeprefix("postgres://")
    return url


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL não está configurada")
    return create_engine(
        normalize_database_url(database_url),
        pool_pre_ping=True,
        pool_recycle=300,
        future=True,
    )


def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def check_database_connection() -> bool:
    with get_engine().connect() as connection:
        return connection.execute(text("SELECT 1")).scalar_one() == 1
