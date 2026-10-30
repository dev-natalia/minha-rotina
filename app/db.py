from collections.abc import Iterator
from datetime import datetime

from sqlalchemy import DateTime, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    # Todo instante é timestamptz (gravado em UTC).
    type_annotation_map = {datetime: DateTime(timezone=True)}


engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    sessao = SessionLocal()
    try:
        yield sessao
    finally:
        sessao.close()
