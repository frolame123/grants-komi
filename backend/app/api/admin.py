"""Управление пользователями — панель администратора (FR-012).

Все маршруты закрыты ролью admin. Каждое действие фиксируется в журнале
аудита с указанием инициатора, объекта и IP-адреса (п. 4.1.4 ТЗ).
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app import mail
from app.api.deps import require_role
from app.audit import write_audit
from app.db import get_db
from app.ratelimit import client_ip
from app.models import AppUser, OrgProfile, PasswordResetToken, RefreshToken
from app.rbac import (
    ROLE_NAMES,
    STATUS_NAMES,
    check_role_change,
    check_status_change,
    is_downgrade,
)
from app.schemas import (
    MessageOut,
    RoleChangeIn,
    StatusChangeIn,
    UserAdminOut,
    UserPageOut,
)
from app.security import generate_token

router = APIRouter(prefix="/api/admin/users", tags=["Администрирование"])

PAGE_SIZE = 20
PASSWORD_RESET_TTL = timedelta(hours=1)


def to_out(user: AppUser, has_profile: bool) -> UserAdminOut:
    return UserAdminOut(
        user_id=user.user_id,
        email=user.email,
        role=user.role,
        role_name=ROLE_NAMES.get(user.role, user.role),
        status=user.status,
        status_name=STATUS_NAMES.get(user.status, user.status),
        created_at=user.created_at,
        last_active_at=user.last_active_at,
        has_profile=has_profile,
        deleted=user.deleted_at is not None,
    )


def load(db: Session, user_id: int) -> AppUser:
    user = db.get(AppUser, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пользователь не найден")
    return user


def revoke_tokens(db: Session, user_id: int) -> None:
    """Отзыв всех токенов обновления пользователя."""
    for token in db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False)
        )
    ):
        token.revoked = True


@router.get("", response_model=UserPageOut)
def list_users(
    db: Session = Depends(get_db),
    admin: AppUser = Depends(require_role("admin")),
    search: str | None = Query(None, max_length=255, description="Часть адреса почты"),
    role: str | None = None,
    user_status: str | None = Query(None, alias="status"),
    active_since: datetime | None = Query(
        None, description="Показать активных начиная с указанной даты"
    ),
    page: int = Query(1, ge=1),
) -> UserPageOut:
    """Список пользователей с фильтрами по роли, статусу и активности."""
    statement = select(AppUser)

    if search:
        statement = statement.where(AppUser.email.ilike(f"%{search}%"))
    if role:
        statement = statement.where(AppUser.role == role)
    if user_status:
        statement = statement.where(AppUser.status == user_status)
    if active_since:
        statement = statement.where(AppUser.last_active_at >= active_since)

    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    statement = statement.order_by(AppUser.user_id).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
    users = list(db.scalars(statement))

    # Один запрос на всю страницу вместо запроса на каждого пользователя
    with_profile = set(
        db.scalars(
            select(OrgProfile.user_id).where(
                OrgProfile.user_id.in_([u.user_id for u in users] or [0])
            )
        )
    )

    return UserPageOut(
        items=[to_out(user, user.user_id in with_profile) for user in users],
        page=page,
        page_size=PAGE_SIZE,
        total=total,
    )


@router.get("/{user_id}", response_model=UserAdminOut)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: AppUser = Depends(require_role("admin")),
) -> UserAdminOut:
    user = load(db, user_id)
    has_profile = db.scalar(select(OrgProfile.profile_id).where(OrgProfile.user_id == user_id))
    return to_out(user, has_profile is not None)


@router.patch("/{user_id}/role", response_model=UserAdminOut)
def change_role(
    user_id: int,
    data: RoleChangeIn,
    request: Request,
    db: Session = Depends(get_db),
    admin: AppUser = Depends(require_role("admin")),
) -> UserAdminOut:
    """Назначение роли. Понижение прав действует немедленно."""
    try:
        check_role_change(admin.user_id, user_id, data.role)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    user = load(db, user_id)
    previous = user.role
    if previous == data.role:
        raise HTTPException(status.HTTP_409_CONFLICT, "Роль уже назначена")

    user.role = data.role
    if is_downgrade(previous, data.role):
        revoke_tokens(db, user.user_id)

    write_audit(
        db,
        action="role_change",
        entity="app_user",
        entity_id=user.user_id,
        user_id=admin.user_id,
        ip=client_ip(request),
    )
    db.commit()

    has_profile = db.scalar(select(OrgProfile.profile_id).where(OrgProfile.user_id == user_id))
    return to_out(user, has_profile is not None)


@router.patch("/{user_id}/status", response_model=UserAdminOut)
def change_status(
    user_id: int,
    data: StatusChangeIn,
    request: Request,
    db: Session = Depends(get_db),
    admin: AppUser = Depends(require_role("admin")),
) -> UserAdminOut:
    """Блокировка и разблокировка учётной записи."""
    try:
        check_status_change(admin.user_id, user_id, data.status)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    user = load(db, user_id)
    if user.deleted_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Учётная запись удалена пользователем")

    user.status = data.status
    if data.status == "blocked":
        revoke_tokens(db, user.user_id)

    write_audit(
        db,
        action="user_block" if data.status == "blocked" else "user_unblock",
        entity="app_user",
        entity_id=user.user_id,
        user_id=admin.user_id,
        ip=client_ip(request),
    )
    db.commit()

    has_profile = db.scalar(select(OrgProfile.profile_id).where(OrgProfile.user_id == user_id))
    return to_out(user, has_profile is not None)


@router.post("/{user_id}/password-reset", response_model=MessageOut)
def send_password_reset(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: AppUser = Depends(require_role("admin")),
) -> MessageOut:
    """Сброс пароля по инициативе администратора.

    Администратор не задаёт пароль сам: он отправляет пользователю ссылку на
    смену. Иначе администратор знал бы чужой пароль, а это нарушает принцип
    «пароль известен только владельцу».
    """
    user = load(db, user_id)
    if user.deleted_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Учётная запись удалена пользователем")

    token = generate_token()
    db.add(
        PasswordResetToken(
            user_id=user.user_id,
            token=token,
            expires_at=datetime.now() + PASSWORD_RESET_TTL,
        )
    )
    write_audit(
        db,
        action="password_reset",
        entity="app_user",
        entity_id=user.user_id,
        user_id=admin.user_id,
        ip=client_ip(request),
    )
    db.commit()

    mail.send_password_reset(user.email, token)
    return MessageOut(detail="Ссылка для смены пароля отправлена пользователю")
