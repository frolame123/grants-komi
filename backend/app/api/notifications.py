"""Уведомления пользователя и настройки рассылки (FR-011)."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models import AppUser, Notification, Program
from app.notifications import TYPE_NAMES
from app.schemas import (
    MessageOut,
    NotificationPageOut,
    NotificationOut,
    NotificationSettingsIn,
    NotificationSettingsOut,
)

router = APIRouter(prefix="/api/notifications", tags=["Уведомления"])

PAGE_SIZE = 20


@router.get("", response_model=NotificationPageOut)
def list_notifications(
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
    unread_only: bool = False,
    page: int = Query(1, ge=1),
) -> NotificationPageOut:
    """Уведомления пользователя со счётчиком непрочитанных (FR-011)."""
    statement = select(Notification, Program).join(
        Program, Program.program_id == Notification.program_id
    ).where(Notification.user_id == user.user_id)
    if unread_only:
        statement = statement.where(Notification.is_read.is_(False))

    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    unread = db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user.user_id, Notification.is_read.is_(False))
    ) or 0

    statement = (
        statement.order_by(Notification.sent_at.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    )

    return NotificationPageOut(
        items=[
            NotificationOut(
                notification_id=notification.notification_id,
                program_id=program.program_id,
                program_title=program.title,
                deadline=program.deadline,
                type=notification.type,
                type_name=TYPE_NAMES.get(notification.type, notification.type),
                sent_at=notification.sent_at,
                is_read=notification.is_read,
            )
            for notification, program in db.execute(statement)
        ],
        page=page,
        page_size=PAGE_SIZE,
        total=total,
        unread=unread,
    )


@router.post("/{notification_id}/read", response_model=MessageOut)
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> MessageOut:
    notification = db.get(Notification, notification_id)
    if notification is None or notification.user_id != user.user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Уведомление не найдено")

    notification.is_read = True
    db.commit()
    return MessageOut(detail="Уведомление отмечено прочитанным")


@router.post("/read-all", response_model=MessageOut)
def mark_all_read(
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> MessageOut:
    db.execute(
        update(Notification)
        .where(Notification.user_id == user.user_id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    db.commit()
    return MessageOut(detail="Все уведомления отмечены прочитанными")


@router.get("/settings", response_model=NotificationSettingsOut)
def get_settings(user: AppUser = Depends(get_current_user)) -> NotificationSettingsOut:
    return NotificationSettingsOut(email_notifications=user.email_notifications)


@router.put("/settings", response_model=NotificationSettingsOut)
def update_settings(
    data: NotificationSettingsIn,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> NotificationSettingsOut:
    """Отказ от рассылки по электронной почте (38-ФЗ, п. 4.2.11 ТЗ).

    Уведомления в интерфейсе системы продолжают приходить: они не покидают
    систему и под требование о согласии на рассылку не подпадают.
    """
    user.email_notifications = data.email_notifications
    db.commit()
    return NotificationSettingsOut(email_notifications=user.email_notifications)
