"""Просмотр журнала аудита администратором (FR-015).

Записи журнала неизменяемы: маршрутов изменения и удаления нет и быть не
должно — иначе журнал перестаёт быть доказательством. Срок хранения по ТЗ —
не менее года, удаление старых записей выполняется вне приложения.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db import get_db
from app.models import AppUser, AuditLog
from app.schemas import AuditOut, AuditPageOut

router = APIRouter(prefix="/api/admin/audit", tags=["Администрирование"])

PAGE_SIZE = 50  # п. 4.2.15 ТЗ: пагинация по 50 записей

ACTION_NAMES = {
    "register": "Регистрация",
    "login": "Вход",
    "logout": "Выход",
    "password_reset": "Сброс пароля",
    "role_change": "Изменение роли",
    "user_block": "Блокировка учётной записи",
    "user_unblock": "Разблокировка учётной записи",
    "account_delete": "Удаление учётной записи",
    "program_create": "Создание карточки программы",
    "program_update": "Правка карточки программы",
    "program_publish": "Публикация программы",
    "program_reject": "Отклонение записи очереди модерации",
    "program_archive": "Архивация программы",
    "dict_propose": "Предложение значения справочника",
    "dict_approve": "Утверждение значения справочника",
    "dict_merge": "Объединение значений справочника",
    "rate_limit_block": "Блокировка по превышению частоты запросов",
}


@router.get("", response_model=AuditPageOut)
def list_audit(
    db: Session = Depends(get_db),
    admin: AppUser = Depends(require_role("admin")),
    user_id: int | None = None,
    action: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = Query(1, ge=1),
) -> AuditPageOut:
    """Записи журнала с фильтрами по пользователю, действию и диапазону дат."""
    statement = select(AuditLog)

    if user_id is not None:
        statement = statement.where(AuditLog.user_id == user_id)
    if action:
        statement = statement.where(AuditLog.action == action)
    if date_from is not None:
        statement = statement.where(AuditLog.created_at >= date_from)
    if date_to is not None:
        statement = statement.where(AuditLog.created_at <= date_to)

    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    statement = (
        statement.order_by(AuditLog.created_at.desc(), AuditLog.audit_id.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    )
    records = list(db.scalars(statement))

    # Адреса авторов действий одним запросом на страницу, а не по одному
    author_ids = {record.user_id for record in records if record.user_id is not None}
    emails = dict(
        db.execute(
            select(AppUser.user_id, AppUser.email).where(AppUser.user_id.in_(author_ids or {0}))
        ).all()
    )

    return AuditPageOut(
        items=[
            AuditOut(
                audit_id=record.audit_id,
                user_id=record.user_id,
                user_email=emails.get(record.user_id),
                action=record.action,
                action_name=ACTION_NAMES.get(record.action, record.action),
                entity=record.entity,
                entity_id=record.entity_id,
                ip_address=record.ip_address,
                details=record.details,
                created_at=record.created_at,
            )
            for record in records
        ],
        page=page,
        page_size=PAGE_SIZE,
        total=total,
    )


@router.get("/actions", response_model=dict[str, str])
def list_actions(admin: AppUser = Depends(require_role("admin"))) -> dict[str, str]:
    """Справочник действий для выпадающего списка фильтра."""
    return ACTION_NAMES
