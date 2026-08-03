"""Удаление собственной учётной записи (FR-013)."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.audit import write_audit
from app.db import get_db
from app.models import AppUser
from app.ratelimit import client_ip
from app.schemas import AccountDeleteIn, MessageOut
from app.security import verify_password

router = APIRouter(prefix="/api/account", tags=["Учётная запись"])


@router.post("/delete", response_model=MessageOut)
def delete_account(
    data: AccountDeleteIn,
    request: Request,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> MessageOut:
    """Удаление учётной записи по запросу пользователя (152-ФЗ, FR-013).

    Подтверждение паролем обязательно: действие необратимо, а токен доступа
    может быть перехвачен. Пароль знает только владелец.

    Данные удаляет функция базы fn_anonymize_user: профиль организации,
    избранное, заявки, уведомления и токены исчезают, сама учётная запись
    обезличивается. Записи журнала аудита сохраняются — они фиксируют
    действия, а не личность, и ссылка на пользователя в них обнуляется
    правилом внешнего ключа при физическом удалении.

    Адрес электронной почты освобождается: повторная регистрация с ним
    создаёт новую пустую учётную запись без восстановления прежних данных
    (FR-001).
    """
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Неверный пароль")

    write_audit(
        db,
        action="account_delete",
        entity="app_user",
        entity_id=user.user_id,
        user_id=user.user_id,
        ip=client_ip(request),
        details="удаление по запросу пользователя",
    )
    db.flush()

    db.execute(text("SELECT fn_anonymize_user(:user_id)"), {"user_id": user.user_id})
    db.commit()

    return MessageOut(
        detail="Учётная запись удалена. Данные профиля, заявки и уведомления стёрты"
    )
