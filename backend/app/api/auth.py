"""Аутентификация: FR-001, FR-002, FR-009, FR-010 и вход в систему."""

import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import mail
from app.api.deps import get_current_user
from app.audit import write_audit
from app.config import settings
from app.db import get_db
from app.models import (
    AppUser,
    EmailConfirmationToken,
    PasswordResetToken,
    RefreshToken,
)
from app.ratelimit import client_ip, email_requests, login_attempts, registrations
from app.schemas import (
    EmailIn,
    LoginIn,
    MessageOut,
    PasswordResetIn,
    RefreshIn,
    RegisterIn,
    TokenPair,
    UserOut,
)
from app.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["Аутентификация"])

CONFIRMATION_TTL = timedelta(hours=24)
PASSWORD_RESET_TTL = timedelta(hours=1)

# Общий ответ на запрос восстановления: существование учётной записи не
# раскрывается (FR-009)
RESET_REPLY = "Если аккаунт существует, письмо отправлено"


class ConfirmOut(BaseModel):
    """Ответ подтверждения адреса: токены выдаются только при первом переходе."""

    detail: str
    access_token: str | None = None
    refresh_token: str | None = None


def issue_tokens(db: Session, user: AppUser) -> TokenPair:
    """Выдать пару токенов и запомнить jti для последующего отзыва (FR-010)."""
    jti = uuid.uuid4().hex
    db.add(
        RefreshToken(
            user_id=user.user_id,
            jti=jti,
            expires_at=datetime.now() + timedelta(days=settings.refresh_token_ttl_days),
        )
    )
    return TokenPair(
        access_token=create_access_token(user.user_id, user.role),
        refresh_token=create_refresh_token(user.user_id, jti),
    )


def revoke_all(db: Session, user_id: int) -> None:
    """Отозвать все токены обновления пользователя (смена пароля, роли, выход)."""
    for token in db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False)
        )
    ):
        token.revoked = True


def too_many(db: Session, request: Request, user_id: int | None = None) -> HTTPException:
    """429 с фиксацией блокировки в журнале аудита (п. 4.1.4 ТЗ)."""
    ip = client_ip(request)
    write_audit(db, action="rate_limit_block", entity="request", user_id=user_id, ip=ip)
    db.commit()
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        "Превышено допустимое число запросов, повторите попытку позже",
    )


@router.post("/register", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
def register(data: RegisterIn, request: Request, db: Session = Depends(get_db)) -> MessageOut:
    """Регистрация нового пользователя (FR-001)."""
    ip = client_ip(request)
    if not registrations.hit(ip):
        raise too_many(db, request)

    if db.scalar(select(AppUser).where(AppUser.email == data.email)):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Учётная запись с таким адресом уже существует"
        )

    user = AppUser(
        email=data.email,
        password_hash=hash_password(data.password),
        role="applicant",
        status="pending",
        pd_consent_at=datetime.now().astimezone(),
    )
    db.add(user)
    db.flush()

    token = generate_token()
    db.add(
        EmailConfirmationToken(
            user_id=user.user_id,
            token=token,
            expires_at=datetime.now() + CONFIRMATION_TTL,
        )
    )
    write_audit(db, action="register", entity="app_user", entity_id=user.user_id, ip=ip)
    db.commit()

    mail.send_confirmation(user.email, token)
    return MessageOut(detail="Письмо со ссылкой подтверждения отправлено на указанный адрес")


@router.post("/resend", response_model=MessageOut)
def resend_confirmation(
    data: EmailIn, request: Request, db: Session = Depends(get_db)
) -> MessageOut:
    """Повторная отправка письма подтверждения, не чаще 1 раза в минуту (FR-001)."""
    if not email_requests.hit(data.email):
        raise too_many(db, request)

    user = db.scalar(select(AppUser).where(AppUser.email == data.email))
    if user and user.status == "pending":
        token = generate_token()
        db.add(
            EmailConfirmationToken(
                user_id=user.user_id,
                token=token,
                expires_at=datetime.now() + CONFIRMATION_TTL,
            )
        )
        db.commit()
        mail.send_confirmation(user.email, token)

    # Существование и состояние учётной записи не раскрываются
    return MessageOut(detail="Если подтверждение требуется, письмо отправлено повторно")


@router.get("/confirm", response_model=ConfirmOut)
def confirm_email(token: str, request: Request, db: Session = Depends(get_db)) -> ConfirmOut:
    """Подтверждение адреса электронной почты по ссылке из письма (FR-002)."""
    record = db.scalar(select(EmailConfirmationToken).where(EmailConfirmationToken.token == token))
    if record is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ссылка недействительна или устарела")

    user = db.get(AppUser, record.user_id)
    if record.used or (user is not None and user.status == "active"):
        # Повторный переход: адрес не изменяется, токены не выдаются
        return ConfirmOut(detail="Адрес уже подтверждён")
    if record.expires_at < datetime.now():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ссылка недействительна или устарела")

    record.used = True
    user.status = "active"
    tokens = issue_tokens(db, user)
    write_audit(
        db,
        action="login",
        entity="app_user",
        entity_id=user.user_id,
        user_id=user.user_id,
        ip=client_ip(request),
    )
    db.commit()
    return ConfirmOut(
        detail="Адрес подтверждён",
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )


@router.post("/login", response_model=TokenPair)
def login(data: LoginIn, request: Request, db: Session = Depends(get_db)) -> TokenPair:
    """Вход: выдача пары токенов (п. 4.1.1 ТЗ)."""
    ip = client_ip(request)
    if login_attempts.exceeded(ip):
        raise too_many(db, request)

    user = db.scalar(select(AppUser).where(AppUser.email == data.email))
    if user is None or not verify_password(data.password, user.password_hash):
        login_attempts.hit(ip)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный адрес или пароль")

    if user.status == "pending":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Адрес электронной почты не подтверждён")
    if user.status == "blocked":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Учётная запись заблокирована")

    login_attempts.reset(ip)
    tokens = issue_tokens(db, user)
    write_audit(
        db,
        action="login",
        entity="app_user",
        entity_id=user.user_id,
        user_id=user.user_id,
        ip=ip,
    )
    db.commit()
    return tokens


@router.post("/refresh", response_model=TokenPair)
def refresh(data: RefreshIn, db: Session = Depends(get_db)) -> TokenPair:
    """Обновление пары токенов. Использованный токен отзывается (ротация)."""
    try:
        payload = decode_token(data.refresh_token, "refresh")
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    record = db.scalar(select(RefreshToken).where(RefreshToken.jti == payload["jti"]))
    if record is None or record.revoked:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Токен отозван")

    user = db.get(AppUser, record.user_id)
    if user is None or user.status != "active":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Учётная запись недоступна")

    record.revoked = True
    tokens = issue_tokens(db, user)
    db.commit()
    return tokens


@router.post("/logout", response_model=MessageOut)
def logout(
    data: RefreshIn,
    request: Request,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> MessageOut:
    """Выход из системы: отзыв токена обновления (FR-010)."""
    try:
        payload = decode_token(data.refresh_token, "refresh")
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    record = db.scalar(select(RefreshToken).where(RefreshToken.jti == payload["jti"]))
    if record is not None and record.user_id == user.user_id:
        record.revoked = True

    write_audit(
        db,
        action="logout",
        entity="app_user",
        entity_id=user.user_id,
        user_id=user.user_id,
        ip=client_ip(request),
    )
    db.commit()
    return MessageOut(detail="Выход выполнен")


@router.post("/password/forgot", response_model=MessageOut)
def forgot_password(
    data: EmailIn, request: Request, db: Session = Depends(get_db)
) -> MessageOut:
    """Запрос ссылки для смены пароля (FR-009)."""
    if not email_requests.hit(data.email):
        raise too_many(db, request)

    user = db.scalar(select(AppUser).where(AppUser.email == data.email))
    if user is not None and user.deleted_at is None:
        token = generate_token()
        db.add(
            PasswordResetToken(
                user_id=user.user_id,
                token=token,
                expires_at=datetime.now() + PASSWORD_RESET_TTL,
            )
        )
        db.commit()
        mail.send_password_reset(user.email, token)

    return MessageOut(detail=RESET_REPLY)


@router.post("/password/reset", response_model=MessageOut)
def reset_password(
    data: PasswordResetIn, request: Request, db: Session = Depends(get_db)
) -> MessageOut:
    """Смена пароля по ссылке из письма; все токены пользователя отзываются (FR-009)."""
    record = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token == data.token))
    if record is None or record.used or record.expires_at < datetime.now():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ссылка недействительна или устарела")

    user = db.get(AppUser, record.user_id)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ссылка недействительна или устарела")

    record.used = True
    user.password_hash = hash_password(data.password)
    revoke_all(db, user.user_id)
    write_audit(
        db,
        action="password_reset",
        entity="app_user",
        entity_id=user.user_id,
        user_id=user.user_id,
        ip=client_ip(request),
    )
    db.commit()
    return MessageOut(detail="Пароль изменён, войдите с новым паролем")


@router.get("/me", response_model=UserOut)
def me(user: AppUser = Depends(get_current_user)) -> AppUser:
    """Текущий пользователь по токену доступа."""
    return user
