"""Правила модерации карточек программ (FR-007).

Здесь собраны решения, которые должны выполняться одинаково независимо от
того, кто наполняет очередь: контент-менеджер вручную или модуль агрегации
(FR-006). Функции сравнения и проверки не обращаются к СУБД.
"""

from datetime import date
from decimal import Decimal

# Поля, изменение которых считается существенным (FR-006). Изменение прочих
# полей — косметическое и применяется без модерации
SIGNIFICANT_FIELDS = ("title", "organizer", "amount", "deadline", "applicant_types")

FIELD_NAMES = {
    "title": "Наименование",
    "organizer": "Организатор",
    "amount": "Сумма",
    "deadline": "Срок подачи",
    "applicant_types": "Типы заявителей",
    "category_id": "Категория",
    "source_url": "Ссылка на первоисточник",
}

MAX_REASON_LENGTH = 300


def snapshot(program) -> dict:
    """Снимок значимых полей карточки для представления «было / стало».

    Значения приводятся к строкам: снимок хранится в JSONB, а дата и
    десятичная сумма в JSON напрямую не сериализуются.
    """
    return {
        "title": program.title,
        "organizer": program.organizer,
        "amount": str(program.amount) if program.amount is not None else None,
        "deadline": program.deadline.isoformat() if program.deadline else None,
        "applicant_types": sorted(t.applicant_type for t in program.applicant_types),
        "category_id": program.category_id,
        "source_url": program.source_url,
    }


def diff(before: dict | None, after: dict) -> list[dict]:
    """Различия двух снимков в виде списка полей со значениями до и после."""
    if not before:
        return []
    changes = []
    for field in after:
        old, new = before.get(field), after[field]
        if old != new:
            changes.append(
                {
                    "field": field,
                    "field_name": FIELD_NAMES.get(field, field),
                    "before": old,
                    "after": new,
                    "significant": field in SIGNIFICANT_FIELDS,
                }
            )
    return changes


def is_significant(before: dict | None, after: dict) -> bool:
    """Есть ли среди изменений хотя бы одно существенное.

    Частичное изменение классифицируется по наивысшей категории затронутых
    полей: одно существенное поле делает существенным весь набор (FR-006).
    """
    return any(change["significant"] for change in diff(before, after))


def check_publishable(category_id: int | None, deadline) -> None:
    """Условие публикации: заполнены категория и срок подачи (FR-007).

    То же требование продублировано ограничением chk_program_published в
    схеме, но проверить его заранее нужно, чтобы вернуть внятное сообщение
    вместо ошибки нарушения ограничения.
    """
    missing = []
    if category_id is None:
        missing.append("категория")
    if deadline is None:
        missing.append("срок подачи")
    if missing:
        raise ValueError(
            "Публикация невозможна: не заполнено — " + ", ".join(missing)
        )


def check_reason(raw: str | None) -> str:
    """Причина отклонения обязательна и ограничена по длине (FR-007)."""
    reason = (raw or "").strip()
    if not reason:
        raise ValueError("Укажите причину отклонения")
    if len(reason) > MAX_REASON_LENGTH:
        raise ValueError(f"Причина длиннее {MAX_REASON_LENGTH} символов")
    return reason


def changed_fields(before: dict, after: dict) -> str:
    """Перечень изменённых полей для записи в журнал аудита."""
    names = [change["field_name"] for change in diff(before, after)]
    return ", ".join(names) if names else "без изменений"


def normalize_amount(value) -> Decimal | None:
    """Сумма приводится к десятичному типу: из формы она приходит числом."""
    return None if value is None else Decimal(str(value))


def restored_values(before: dict) -> dict:
    """Значения снимка, приведённые обратно к типам колонок.

    Нужно при отклонении изменения: парсер уже записал новые данные в
    карточку, и отклонение обязано вернуть прежнее содержимое (FR-007).
    В снимке сумма и дата хранятся строками, потому что JSONB не знает ни
    десятичного типа, ни типа даты.
    """
    return {
        "title": before["title"],
        "organizer": before["organizer"],
        "amount": normalize_amount(before["amount"]),
        "deadline": date.fromisoformat(before["deadline"]) if before["deadline"] else None,
        "category_id": before["category_id"],
        "source_url": before["source_url"],
        "applicant_types": list(before["applicant_types"]),
    }
