"""Самопроверка нормализации и ядра агрегации (FR-006).

Проверяются разбор разнородных записей дат и сумм, отпечаток содержимого и
правило отбраковки прогона при вероятном изменении вёрстки источника.

Запуск:  python check_aggregation.py
"""

from datetime import date
from decimal import Decimal

from app.aggregation import check_run_sanity, content_hash
from app.parsers import RawProgram
from app.parsers.normalize import (
    clean_text,
    parse_amount,
    parse_applicant_types,
    parse_date,
)


def card(**kwargs) -> RawProgram:
    defaults = dict(
        title="Грант на развитие социального предпринимательства",
        organizer="Минэкономразвития Республики Коми",
        source_url="https://econom.rkomi.ru/grants/social-2026",
        amount=Decimal("500000.00"),
        deadline=date(2026, 9, 15),
        applicant_types=["IP", "OOO"],
    )
    return RawProgram(**{**defaults, **kwargs})


def check_dates() -> None:
    """Сроки на сайтах записаны как угодно, дата должна получаться одна."""
    expected = date(2026, 7, 15)
    for raw in (
        "2026-07-15",
        "15.07.2026",
        "15/07/2026",
        "до 15.07.2026",
        "Приём заявок до 15 июля 2026 г.",
        "  15 Июля 2026  ",
    ):
        assert parse_date(raw) == expected, f"не разобрано: {raw!r}"

    for raw in (None, "", "в марте", "срок уточняется", "31.02.2026"):
        assert parse_date(raw) is None, f"не должно разбираться: {raw!r}"


def check_amounts() -> None:
    """Суммы приходят с разделителями, приставками и разной пунктуацией."""
    assert parse_amount("500000") == Decimal("500000.00")
    assert parse_amount("500 000 руб.") == Decimal("500000.00")
    assert parse_amount("1 000 000 рублей") == Decimal("1000000.00")
    assert parse_amount("1.000.000") == Decimal("1000000.00"), "точка как разделитель разрядов"
    assert parse_amount("до 1 млн рублей") == Decimal("1000000.00")
    assert parse_amount("500 тыс. руб.") == Decimal("500000.00")
    assert parse_amount("1,5 млн") == Decimal("1500000.00"), "запятая как десятичный разделитель"

    for raw in (None, "", "по решению комиссии", "не указана"):
        assert parse_amount(raw) is None, f"не должно разбираться: {raw!r}"


def check_applicant_types() -> None:
    """Типы заявителей извлекаются из текстового описания требований."""
    assert parse_applicant_types("Для ИП и юридических лиц") == ["IP", "OOO"]
    assert parse_applicant_types("социально ориентированные НКО") == ["NKO"]
    assert parse_applicant_types("самозанятые граждане") == ["SMZ"]
    assert parse_applicant_types("Требования уточняются") == []
    assert parse_applicant_types(None) == []


def check_text_cleanup() -> None:
    assert clean_text("  Грант   на   развитие  ", 100) == "Грант на развитие"
    assert clean_text("а" * 500, 300) == "а" * 300, "обрезка по длине колонки"
    assert clean_text("   ", 100) is None


def check_hash() -> None:
    """Отпечаток меняется при любом значимом изменении и только при нём."""
    base = content_hash(card())
    assert content_hash(card()) == base, "одинаковые карточки — одинаковый отпечаток"

    for changed in (
        card(title="Другое наименование"),
        card(amount=Decimal("750000.00")),
        card(deadline=date(2026, 10, 1)),
        card(applicant_types=["NKO"]),
        card(organizer="Другой организатор"),
    ):
        assert content_hash(changed) != base, "изменение не отразилось в отпечатке"

    # Порядок типов заявителей значения не имеет: это множество, а не список
    assert content_hash(card(applicant_types=["OOO", "IP"])) == base

    # Разделитель полей исключает склейку: «АБ»+«В» и «А»+«БВ» различимы
    left = content_hash(card(title="АБ", organizer="В"))
    right = content_hash(card(title="А", organizer="БВ"))
    assert left != right, "поля склеиваются без разделителя"


def check_run_sanity_rules() -> None:
    """Прогон отбрасывается целиком, если разбор явно сломался."""
    good = [card(source_url=f"https://example.org/{n}") for n in range(10)]
    assert check_run_sanity(good) is None

    assert check_run_sanity([]) is not None, "ноль карточек — вёрстка изменилась"

    broken = [card(title=None) for _ in range(6)] + [card() for _ in range(4)]
    assert check_run_sanity(broken) is not None, "больше половины неразобранных"

    acceptable = [card(title=None) for _ in range(4)] + [card() for _ in range(6)]
    assert check_run_sanity(acceptable) is None, "меньше половины — прогон принимается"


def check_completeness() -> None:
    """Карточка без обязательных полей не может быть принята."""
    assert card().complete
    assert not card(title=None).complete
    assert not card(organizer=None).complete
    assert not card(source_url=None).complete
    # Незаполненный срок допустим: п. 3.5 ТЗ описывает такие программы
    assert card(deadline=None).complete


def main() -> None:
    for check in (
        check_dates,
        check_amounts,
        check_applicant_types,
        check_text_cleanup,
        check_hash,
        check_run_sanity_rules,
        check_completeness,
    ):
        check()
        print(f"OK: {check.__name__}")


if __name__ == "__main__":
    main()
