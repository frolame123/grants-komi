"""Общие зависимости API: текущий пользователь и проверка роли (RBAC)."""

from collections.abc import Callable
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AppUser
from app.security import decode_token

bearer = HTTPBearer(auto_error=False)

ACTIVITY_INTERVAL = timedelta(minutes=5)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> AppUser:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Требуется авторизация")
    try:
        payload = decode_token(credentials.credentials, "access")
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    user = db.get(AppUser, int(payload["sub"]))
    if user is None or user.status != "active":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Учётная запись недоступна")

    touch_activity(db, user)
    return user


def touch_activity(db: Session, user: AppUser) -> None:
    """Отметка последней активности для фильтра в панели управления (FR-012).

    Запись выполняется не чаще одного раза в пять минут: обновление на каждый
    запрос превратило бы любое чтение каталога в запись в базу.
    """
    now = datetime.now()
    if user.last_active_at is None or now - user.last_active_at > ACTIVITY_INTERVAL:
        user.last_active_at = now
        db.commit()


def require_role(*roles: str) -> Callable[[AppUser], AppUser]:
    """Ограничение доступа по роли.

    Роль берётся из записи в БД, а не из токена: понижение роли и блокировка
    вступают в силу немедленно (п. 4.1.4 ТЗ).
    """

    def dependency(user: AppUser = Depends(get_current_user)) -> AppUser:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Недостаточно прав")
        return user

    return dependency
