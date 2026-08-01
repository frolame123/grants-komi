"""Контур аутентификации: пароли и JWT-токены (п. 4.1.1, 4.1.4 ТЗ).

Пароль хранится только в виде bcrypt-хэша. Доступ — пара токенов:
access (30 минут, без состояния) и refresh (7 суток, отзывается через
таблицу refresh_token при выходе и смене пароля).
"""

import re
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Политика пароля (FR-001): не менее 8 символов, буквы обоих регистров, цифра
PASSWORD_RULES = (
    (lambda p: len(p) >= 8, "Пароль должен содержать не менее 8 символов"),
    (lambda p: re.search(r"[a-zа-яё]", p), "Пароль должен содержать строчную букву"),
    (lambda p: re.search(r"[A-ZА-ЯЁ]", p), "Пароль должен содержать прописную букву"),
    (lambda p: re.search(r"\d", p), "Пароль должен содержать цифру"),
)


def validate_password(password: str) -> None:
    """Проверка пароля по политике. Возбуждает ValueError с русским текстом."""
    for rule, message in PASSWORD_RULES:
        if not rule(password):
            raise ValueError(message)


def hash_password(raw: str) -> str:
    return pwd_context.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    return pwd_context.verify(raw, hashed)


def generate_token() -> str:
    """Одноразовый токен для писем подтверждения и восстановления."""
    return secrets.token_urlsafe(32)


def _encode(payload: dict, ttl: timedelta) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {**payload, "iat": now, "exp": now + ttl},
        settings.secret_key,
        algorithm=settings.algorithm,
    )


def create_access_token(user_id: int, role: str) -> str:
    """Токен доступа: идентификатор и роль для проверок RBAC без обращения к БД."""
    return _encode(
        {"sub": str(user_id), "role": role, "type": "access"},
        timedelta(minutes=settings.access_token_ttl_min),
    )


def create_refresh_token(user_id: int, jti: str) -> str:
    """Токен обновления: jti хранится в БД, что и позволяет его отозвать."""
    return _encode(
        {"sub": str(user_id), "jti": jti, "type": "refresh"},
        timedelta(days=settings.refresh_token_ttl_days),
    )


def decode_token(token: str, expected_type: str) -> dict:
    """Разбор и проверка токена. Возбуждает ValueError при любой проблеме."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError as exc:
        raise ValueError("Токен недействителен или устарел") from exc
    if payload.get("type") != expected_type:
        raise ValueError("Неверный тип токена")
    return payload
