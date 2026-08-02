"""Приведение данных источников к единому виду (FR-006).

Сайты пишут сроки и суммы как придётся: «до 15.07.2026», «15 июля 2026 г.»,
«2026-07-15», «до 1 млн рублей», «500 000 руб.». Модуль агрегации обязан
получить из этого дату и число, иначе карточка не пройдёт проверку схемы.

Функции ничего не знают ни о сети, ни о СУБД: их можно проверять по отдельным
строкам.
"""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

MONTHS = {
    "янв": 1, "фев": 2, "мар": 3, "апр": 4, "мая": 5, "май": 5, "июн": 6,
    "июл": 7, "авг": 8, "сен": 9, "окт": 10, "ноя": 11, "дек": 12,
}

MULTIPLIERS = {
    "тыс": Decimal(1_000),
    "млн": Decimal(1_000_000),
    "млрд": Decimal(1_000_000_000),
}

DATE_DIGITS = re.compile(r"(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})")
DATE_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
DATE_WORDS = re.compile(r"(\d{1,2})\s+([а-яё]{3,})\.?\s+(\d{4})", re.IGNORECASE)

AMOUNT = re.compile(r"(\d[\d\s .,]*)\s*(тыс|млн|млрд)?", re.IGNORECASE)


def parse_date(raw: str | None) -> date | None:
    """Дата из произвольной записи. None, если распознать не удалось.

    Нераспознанный срок — не ошибка разбора: п. 3.5 ТЗ прямо описывает случай
    «программа без чётко указанного срока подачи», такая карточка не может
    быть опубликована автоматически и ждёт контент-менеджера.
    """
    if not raw:
        return None
    text = raw.strip().lower()

    iso = DATE_ISO.search(text)
    if iso:
        return _safe_date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))

    digits = DATE_DIGITS.search(text)
    if digits:
        return _safe_date(int(digits.group(3)), int(digits.group(2)), int(digits.group(1)))

    words = DATE_WORDS.search(text)
    if words:
        month = MONTHS.get(words.group(2)[:3])
        if month:
            return _safe_date(int(words.group(3)), month, int(words.group(1)))

    return None


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        # «31 февраля» и подобное: источник ошибся, срок считается неуказанным
        return None


def parse_amount(raw: str | None) -> Decimal | None:
    """Сумма из произвольной записи. None, если распознать не удалось.

    Учитываются разделители разрядов, включая неразрывный пробел, запятая как
    десятичный разделитель и приставки «тыс», «млн», «млрд».
    """
    if not raw:
        return None
    if isinstance(raw, (int, float, Decimal)):
        return Decimal(str(raw))

    match = AMOUNT.search(raw.strip().lower())
    if not match:
        return None

    number = match.group(1)
    number = re.sub(r"[\s ]", "", number)
    # Разделитель разрядов точкой («1.000.000») отличается от десятичной точки
    # тем, что после него ровно три цифры и групп больше одной
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", number):
        number = number.replace(".", "")
    number = number.replace(",", ".")

    try:
        value = Decimal(number)
    except InvalidOperation:
        return None

    multiplier = MULTIPLIERS.get(match.group(2) or "")
    if multiplier:
        value *= multiplier

    value = value.quantize(Decimal("0.01"))
    return value if value > 0 else None


def clean_text(raw: str | None, limit: int) -> str | None:
    """Схлопывание пробелов и обрезка по длине колонки."""
    if not raw:
        return None
    text = re.sub(r"\s+", " ", raw).strip()
    return text[:limit] if text else None


def parse_applicant_types(raw: str | None) -> list[str]:
    """Типы заявителей из текстового описания требований.

    Источники пишут их словами: «для ИП и юридических лиц», «социально
    ориентированные НКО». Классификатор типов задан ТЗ и закрыт, поэтому
    достаточно поиска ключевых слов.
    """
    if not raw:
        return []
    text = raw.lower()
    found = set()

    if re.search(r"\bип\b|индивидуальн\w* предприниматель", text):
        found.add("IP")
    if re.search(r"\bооо\b|юридическ\w* лиц|организаци", text):
        found.add("OOO")
    if re.search(r"\bнко\b|некоммерческ", text):
        found.add("NKO")
    if re.search(r"самозанят", text):
        found.add("SMZ")

    return sorted(found)


def as_datetime(value: date | None) -> datetime | None:
    return datetime(value.year, value.month, value.day) if value else None
