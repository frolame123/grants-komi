"""Самопроверка правил модерации карточек (FR-007).

Проверяется сравнение снимков «было / стало», классификация изменений по
существенности и условия публикации и отклонения.

Запуск:  python check_moderation.py
"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.moderation import (
    changed_fields,
    check_publishable,
    check_reason,
    diff,
    is_significant,
    restored_values,
    snapshot,
)


def program(**kwargs) -> SimpleNamespace:
    defaults = dict(
        title="Грант на развитие социального предпринимательства",
        organizer="Минэкономразвития Республики Коми",
        amount=500000,
        deadline=date(2026, 9, 15),
        applicant_types=[SimpleNamespace(applicant_type="OOO")],
        category_id=1,
        source_url="https://econom.rkomi.ru/grants/social-2026",
    )
    return SimpleNamespace(**{**defaults, **kwargs})


def rejects(func, *args) -> bool:
    try:
        func(*args)
    except ValueError:
        return True
    return False


def check_snapshot() -> None:
    """Снимок должен быть пригоден для хранения в JSONB."""
    data = snapshot(program())
    assert data["amount"] == "500000", "сумма приводится к строке"
    assert data["deadline"] == "2026-09-15", "дата в формате ISO 8601"
    assert data["applicant_types"] == ["OOO"]
    assert isinstance(data["category_id"], int)


def check_no_changes() -> None:
    before = snapshot(program())
    assert diff(before, before) == [], "одинаковые снимки расхождений не дают"
    assert not is_significant(before, before)
    assert changed_fields(before, before) == "без изменений"
    assert diff(None, before) == [], "для новой карточки сравнивать не с чем"


def check_significant_changes() -> None:
    before = snapshot(program())

    for changed, field in (
        (program(title="Грант на развитие социальных проектов"), "Наименование"),
        (program(organizer="Фонд «Агентство регионального развития»"), "Организатор"),
        (program(amount=750000), "Сумма"),
        (program(deadline=date(2026, 10, 1)), "Срок подачи"),
        (
            program(applicant_types=[SimpleNamespace(applicant_type="NKO")]),
            "Типы заявителей",
        ),
    ):
        after = snapshot(changed)
        assert is_significant(before, after), f"изменение поля «{field}» существенно"
        assert changed_fields(before, after) == field


def check_cosmetic_change() -> None:
    """Изменение ссылки на первоисточник существенным не считается."""
    before = snapshot(program())
    after = snapshot(program(source_url="https://econom.rkomi.ru/grants/social-2026?utm=1"))

    assert diff(before, after), "расхождение должно быть найдено"
    assert not is_significant(before, after), "косметическое изменение не требует модерации"


def check_partial_change() -> None:
    """Набор из существенного и косметического изменений считается существенным."""
    before = snapshot(program())
    after = snapshot(program(amount=750000, source_url="https://example.org/other"))
    assert is_significant(before, after)


def check_publication_rules() -> None:
    check_publishable(1, date(2026, 9, 15))

    assert rejects(check_publishable, None, date(2026, 9, 15)), "без категории"
    assert rejects(check_publishable, 1, None), "без срока подачи"
    assert rejects(check_publishable, None, None), "без того и другого"


def check_restoration() -> None:
    """Снимок разворачивается обратно в значения колонок без потерь."""
    original = program()
    values = restored_values(snapshot(original))

    assert values["title"] == original.title
    assert values["amount"] == Decimal("500000"), "сумма возвращается десятичным числом"
    assert values["deadline"] == date(2026, 9, 15), "дата возвращается типом date"
    assert values["applicant_types"] == ["OOO"]
    assert values["category_id"] == 1

    # Незаполненные значения переживают преобразование в обе стороны
    empty = restored_values(snapshot(program(amount=None, deadline=None)))
    assert empty["amount"] is None and empty["deadline"] is None


def check_rejection_reason() -> None:
    assert check_reason("  Срок не определён  ") == "Срок не определён"

    assert rejects(check_reason, ""), "пустая причина"
    assert rejects(check_reason, "   "), "причина из пробелов"
    assert rejects(check_reason, None), "причина не указана"
    assert rejects(check_reason, "п" * 301), "причина длиннее 300 символов"


def main() -> None:
    for check in (
        check_snapshot,
        check_no_changes,
        check_significant_changes,
        check_cosmetic_change,
        check_partial_change,
        check_publication_rules,
        check_restoration,
        check_rejection_reason,
    ):
        check()
        print(f"OK: {check.__name__}")


if __name__ == "__main__":
    main()
