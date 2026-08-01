"""Самопроверка бизнес-логики: контрольное число ИНН и подбор программ.

Проверяются правила, которые нельзя увидеть по коду глазами: алгоритм ФНС
и начисление баллов соответствия. СУБД не требуется — подбор работает с
любыми объектами, у которых есть нужные атрибуты.

Запуск:  python check_business.py
"""

from datetime import date, timedelta
from types import SimpleNamespace

from app.inn import WEIGHTS_10, WEIGHTS_11, WEIGHTS_12, _control_digit, validate_inn
from app.matching import match_score, passes_hard_filter, select_programs

TODAY = date(2026, 7, 27)


def make_inn(prefix: str) -> str:
    """Достроить ИНН до корректного по алгоритму ФНС (9 или 10 цифр на входе)."""
    if len(prefix) == 9:
        return prefix + str(_control_digit(prefix, WEIGHTS_10))
    eleventh = _control_digit(prefix, WEIGHTS_11)
    twelfth = _control_digit(prefix + str(eleventh), WEIGHTS_12)
    return f"{prefix}{eleventh}{twelfth}"


def program(**kwargs) -> SimpleNamespace:
    defaults = dict(
        status="PUB",
        deadline=TODAY + timedelta(days=30),
        category_id=1,
        title="Грант на развитие социального предпринимательства",
        applicant_types=[SimpleNamespace(applicant_type="OOO")],
        regions=[SimpleNamespace(region="Республика Коми")],
    )
    return SimpleNamespace(**{**defaults, **kwargs})


def profile(**kwargs) -> SimpleNamespace:
    defaults = dict(
        org_type="OOO",
        category_id=1,
        region="Республика Коми",
        goal="Развитие мастерской социального направления",
    )
    return SimpleNamespace(**{**defaults, **kwargs})


def check_inn() -> None:
    ooo = make_inn("110123456")
    validate_inn(ooo, "OOO")

    ip = make_inn("1109876543")
    validate_inn(ip, "IP")

    # испорченное контрольное число
    broken = ooo[:9] + str((int(ooo[9]) + 1) % 10)
    for value, org_type, reason in (
        (broken, "OOO", "неверное контрольное число"),
        (ooo, "IP", "10 цифр при типе ИП"),
        (ip, "OOO", "12 цифр при типе ООО"),
        ("11012345a7", "OOO", "буква в номере"),
        (ooo, "XXX", "неизвестный тип организации"),
    ):
        try:
            validate_inn(value, org_type)
        except ValueError:
            continue
        raise AssertionError(f"ИНН принят, хотя не должен: {reason}")


def check_hard_filter() -> None:
    assert passes_hard_filter(program(), profile(), TODAY)

    for bad, reason in (
        (program(status="MOD"), "программа не опубликована"),
        (program(status="ARCH"), "программа в архиве"),
        (program(deadline=TODAY - timedelta(days=1)), "срок подачи истёк"),
        (program(deadline=None), "срок подачи не задан"),
        (
            program(applicant_types=[SimpleNamespace(applicant_type="NKO")]),
            "тип заявителя не совпадает",
        ),
    ):
        assert not passes_hard_filter(bad, profile(), TODAY), f"фильтр пропустил: {reason}"


def check_score() -> None:
    # все четыре условия выполнены — максимум
    assert match_score(program(), profile(), TODAY) == 100

    # отрасль не совпала
    assert match_score(program(category_id=2), profile(), TODAY) == 60
    # регион не совпал
    assert match_score(program(regions=[]), profile(), TODAY) == 70
    # цель не пересекается с назначением программы по словам
    assert match_score(program(), profile(goal="Закупка тракторов"), TODAY) == 80
    # до срока меньше 14 дней
    assert match_score(program(deadline=TODAY + timedelta(days=5)), profile(), TODAY) == 90
    # ничего не совпало
    assert (
        match_score(
            program(category_id=2, regions=[], deadline=TODAY + timedelta(days=3)),
            profile(goal=None),
            TODAY,
        )
        == 0
    )
    # короткие слова пересечением не считаются
    assert match_score(program(title="Грант для НКО"), profile(goal="для"), TODAY) == 80


def check_selection_order() -> None:
    weak = program(category_id=2, regions=[], title="Субсидия")
    strong = program()
    skipped = program(status="DRAFT")

    # у weak совпадает только запас по сроку — 10 баллов
    result = select_programs([weak, strong, skipped], profile(), TODAY)
    assert [score for _, score in result] == [100, 10], "сортировка по убыванию баллов"
    assert result[0][0] is strong
    assert all(p is not skipped for p, _ in result), "неопубликованные не попадают в подбор"


def main() -> None:
    for check in (check_inn, check_hard_filter, check_score, check_selection_order):
        check()
        print(f"OK: {check.__name__}")


if __name__ == "__main__":
    main()
