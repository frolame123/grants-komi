"""Самопроверка регламента ведения справочников (FR-016).

Проверяются правила, от которых зависит целостность справочника: приведение
наименования к каноническому виду, обнаружение дублей без учёта регистра и
условия объединения значений.

Запуск:  python check_dictionaries.py
"""

from app.dictionaries import (
    APPROVED,
    MERGED,
    PROPOSED,
    check_approve,
    check_merge,
    check_unique,
    normalize_name,
)


def rejects(func, *args) -> bool:
    try:
        func(*args)
    except ValueError:
        return True
    return False


def check_normalization() -> None:
    """Лишние пробелы не должны порождать разные значения справочника."""
    assert normalize_name("  Экология  и   природопользование ") == "Экология и природопользование"
    assert normalize_name("Культура") == "Культура"

    assert rejects(normalize_name, " к "), "наименование из одной буквы"
    assert rejects(normalize_name, "   "), "пустое наименование"
    assert rejects(normalize_name, "к" * 101), "наименование длиннее 100 символов"


def check_duplicates() -> None:
    """Дубль определяется без учёта регистра: ограничение UNIQUE его пропустит."""
    existing = {"Экология", "Культура и творчество"}

    check_unique("Молодёжные инициативы", existing)  # нового значения нет — годится

    assert rejects(check_unique, "Экология", existing)
    assert rejects(check_unique, "экология", existing), "регистр не должен создавать дубль"
    assert rejects(check_unique, "ЭКОЛОГИЯ", existing)


def check_approval() -> None:
    check_approve(PROPOSED)  # предложенное утверждается

    assert rejects(check_approve, APPROVED), "повторное утверждение"
    assert rejects(check_approve, MERGED), "утверждение объединённого значения"


def check_merging() -> None:
    check_merge(1, PROPOSED, 2, APPROVED)  # дубль объединяется с утверждённым
    check_merge(1, APPROVED, 2, APPROVED)

    assert rejects(check_merge, 1, APPROVED, 1, APPROVED), "объединение само с собой"
    assert rejects(check_merge, 1, MERGED, 2, APPROVED), "повторное объединение"
    assert rejects(check_merge, 1, APPROVED, 2, PROPOSED), "цель ещё не утверждена"
    assert rejects(check_merge, 1, APPROVED, 2, MERGED), "цель сама объединена"


def main() -> None:
    for check in (check_normalization, check_duplicates, check_approval, check_merging):
        check()
        print(f"OK: {check.__name__}")


if __name__ == "__main__":
    main()
