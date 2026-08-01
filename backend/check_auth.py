"""Самопроверка контура аутентификации без обращения к СУБД.

Проверяются правила, от которых зависит безопасность: политика пароля,
хэширование, разбор токенов и счётчик ограничения частоты запросов.

Запуск:  python check_auth.py
"""

import time

from app.ratelimit import SlidingWindow
from app.schemas import RegisterIn
from app.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    validate_password,
    verify_password,
)


def check_password_policy() -> None:
    validate_password("Parol123")  # 8 символов, оба регистра, цифра — годится

    for bad in ("Parol1", "parol123", "PAROL123", "ParolParol"):
        try:
            validate_password(bad)
        except ValueError:
            continue
        raise AssertionError(f"пароль {bad!r} не должен проходить политику")


def check_hashing() -> None:
    hashed = hash_password("Parol123")
    assert hashed != "Parol123", "пароль не должен храниться в открытом виде"
    assert verify_password("Parol123", hashed)
    assert not verify_password("Parol124", hashed)
    # соль: два хэша одного пароля различаются
    assert hash_password("Parol123") != hashed


def check_tokens() -> None:
    access = create_access_token(42, "moderator")
    payload = decode_token(access, "access")
    assert payload["sub"] == "42" and payload["role"] == "moderator"

    refresh = create_refresh_token(42, "abc")
    assert decode_token(refresh, "refresh")["jti"] == "abc"

    # токен обновления не должен приниматься там, где ждут токен доступа
    for token, expected in ((refresh, "access"), (access, "refresh"), ("мусор", "access")):
        try:
            decode_token(token, expected)
        except ValueError:
            continue
        raise AssertionError(f"токен принят как {expected}, хотя не должен")


def check_registration_schema() -> None:
    ok = RegisterIn(
        email="user@example.com",
        password="Parol123",
        password_confirm="Parol123",
        pd_consent=True,
    )
    assert ok.email == "user@example.com"

    # без согласия на обработку ПД и при несовпадении паролей — отказ (FR-001)
    for kwargs in (
        {"password_confirm": "Parol124", "pd_consent": True},
        {"password_confirm": "Parol123", "pd_consent": False},
    ):
        try:
            RegisterIn(email="user@example.com", password="Parol123", **kwargs)
        except ValueError:
            continue
        raise AssertionError(f"схема приняла недопустимые данные: {kwargs}")


def check_rate_limit() -> None:
    window = SlidingWindow(limit=3, window_seconds=1)
    assert all(window.hit("ip") for _ in range(3)), "первые попытки должны проходить"
    assert not window.hit("ip"), "четвёртая попытка должна упереться в лимит"
    assert window.exceeded("ip")
    assert not window.exceeded("другой-ip"), "лимит считается по каждому ключу отдельно"

    # Граница: при лимите 3 после трёх событий следующее уже запрещено.
    # Строгое сравнение здесь давало бы одну лишнюю попытку сверх разрешённых
    boundary = SlidingWindow(limit=3, window_seconds=60)
    for number in range(1, 4):
        assert not boundary.exceeded("ip"), f"попытка {number} должна проходить"
        boundary.hit("ip")
    assert boundary.exceeded("ip"), "четвёртая попытка должна быть отклонена"

    time.sleep(1.1)  # окно сдвинулось — счётчик освободился
    assert not window.exceeded("ip")

    window.hit("ip")
    window.reset("ip")
    assert not window.exceeded("ip")


def main() -> None:
    for check in (
        check_password_policy,
        check_hashing,
        check_tokens,
        check_registration_schema,
        check_rate_limit,
    ):
        check()
        print(f"OK: {check.__name__}")


if __name__ == "__main__":
    main()
