"""Подключение к СУБД и фабрика сессий.

ponytail: синхронный SQLAlchemy. Расчётная нагрузка — 10 одновременных
пользователей (п. 4.3.4 ТЗ), FastAPI выполняет `def`-эндпоинты в пуле
потоков. Переход на async-движок — если профилирование покажет упор в БД.
"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """Зависимость FastAPI: сессия на запрос."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
