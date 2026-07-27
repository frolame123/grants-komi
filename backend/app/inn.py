"""Проверка ИНН по алгоритму контрольного числа ФНС (FR-003).

Длина зависит от организационно-правовой формы: 10 цифр у юридического
лица, 12 — у индивидуального предпринимателя, самозанятого и НКО-заявителя,
зарегистрированного как физическое лицо (ограничение chk_org_profile_inn).
"""

WEIGHTS_10 = (2, 4, 10, 3, 5, 9, 4, 6, 8)
WEIGHTS_11 = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
WEIGHTS_12 = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)

LENGTH_BY_TYPE = {"OOO": 10, "IP": 12, "NKO": 12, "SMZ": 12}


def _control_digit(digits: str, weights: tuple[int, ...]) -> int:
    return sum(int(d) * w for d, w in zip(digits, weights)) % 11 % 10


def validate_inn(inn: str, org_type: str) -> None:
    """Проверка ИНН. Возбуждает ValueError с текстом для поля формы."""
    if not inn.isdigit():
        raise ValueError("ИНН должен содержать только цифры")

    expected_length = LENGTH_BY_TYPE.get(org_type)
    if expected_length is None:
        raise ValueError("Неизвестный тип организации")
    if len(inn) != expected_length:
        raise ValueError(f"ИНН должен содержать {expected_length} цифр")

    if expected_length == 10:
        valid = _control_digit(inn[:9], WEIGHTS_10) == int(inn[9])
    else:
        valid = _control_digit(inn[:10], WEIGHTS_11) == int(inn[10]) and _control_digit(
            inn[:11], WEIGHTS_12
        ) == int(inn[11])

    if not valid:
        raise ValueError("Неверный ИНН")
