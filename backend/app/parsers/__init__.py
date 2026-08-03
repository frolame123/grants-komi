"""Адаптеры внешних источников (FR-006).

Перечень источников закрыт (п. 3.2 ТЗ): каждый требует отдельного адаптера,
добавление нового оформляется изменением технического задания.

Адаптер обязан уметь одно: вернуть список нормализованных карточек. Всё
остальное — сравнение с базой, классификация изменений, наполнение очереди
модерации — общее и живёт в app/aggregation.py.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Protocol

# Поля, без которых карточка считается неразобранной. Доля таких карточек
# больше половины означает вероятное изменение вёрстки источника (FR-006)
REQUIRED_FIELDS = ("title", "organizer", "source_url")


@dataclass
class RawProgram:
    """Карточка программы, приведённая к виду системы."""

    title: str | None = None
    organizer: str | None = None
    source_url: str | None = None
    amount: Decimal | None = None
    deadline: date | None = None
    applicant_types: list[str] = field(default_factory=list)
    regions: list[str] = field(default_factory=lambda: ["Республика Коми"])
    extra: dict = field(default_factory=dict)

    @property
    def complete(self) -> bool:
        """Заполнены ли поля, без которых карточку нельзя принять."""
        return all(getattr(self, name) for name in REQUIRED_FIELDS)


class SourceAdapter(Protocol):
    """Контракт адаптера источника.

    Реализация загружает страницы и разбирает их, но наружу отдаёт только
    список карточек. Благодаря этому ядро агрегации не зависит ни от способа
    загрузки, ни от разметки конкретного сайта, и проверяется на списках,
    собранных вручную.
    """

    source_name: str

    async def fetch(self) -> list[RawProgram]:
        """Вернуть карточки источника. Ошибки сети возбуждают исключение."""
        ...
