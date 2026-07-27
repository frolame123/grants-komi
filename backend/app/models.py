"""Модели SQLAlchemy — отображение схемы БД версии 2 (db/schema.sql).

Схема — единственный источник правды: ограничения CHECK / UNIQUE и функция
fn_anonymize_user заданы в SQL и здесь не дублируются. Модели описывают
только структуру и связи, необходимые ORM.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CHAR,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class AppUser(Base):
    """Пользователь системы (стержневая сущность)."""

    __tablename__ = "app_user"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="applicant")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    pd_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    profile: Mapped["OrgProfile | None"] = relationship(back_populates="user")
    favorites: Mapped[list["Favorite"]] = relationship(back_populates="user")
    applications: Mapped[list["Application"]] = relationship(back_populates="user")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="user")


class EmailConfirmationToken(Base):
    """Токен подтверждения адреса эл. почты, срок 24 часа (FR-002)."""

    __tablename__ = "email_confirmation_token"

    token_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.user_id", ondelete="CASCADE"))
    token: Mapped[str] = mapped_column(String(255), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )


class PasswordResetToken(Base):
    """Токен восстановления пароля, срок 1 час (FR-009)."""

    __tablename__ = "password_reset_token"

    token_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.user_id", ondelete="CASCADE"))
    token: Mapped[str] = mapped_column(String(255), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )


class OrgProfile(Base):
    """Профиль организации-заявителя, связь 1:1 с app_user (FR-003)."""

    __tablename__ = "org_profile"

    profile_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("app_user.user_id", ondelete="CASCADE"), unique=True
    )
    org_type: Mapped[str] = mapped_column(String(10))
    inn: Mapped[str] = mapped_column(String(12), unique=True)
    city: Mapped[str] = mapped_column(String(100))
    street: Mapped[str | None] = mapped_column(String(150))
    house: Mapped[str | None] = mapped_column(String(20))
    org_size: Mapped[str | None] = mapped_column(String(20))
    goal: Mapped[str | None] = mapped_column(String(300))
    region: Mapped[str] = mapped_column(
        String(100), server_default=text("'Республика Коми'")
    )

    user: Mapped[AppUser] = relationship(back_populates="profile")


class Source(Base):
    """Источник сведений о программах (закрытый перечень, п. 3.2 ТЗ)."""

    __tablename__ = "source"

    source_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True)
    url: Mapped[str] = mapped_column(String(500))
    schedule: Mapped[str] = mapped_column(String(50), default="daily")


class Category(Base):
    """Категория программы (справочник, FR-016)."""

    __tablename__ = "category"

    category_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)


class Program(Base):
    """Программа грантовой поддержки (стержневая сущность)."""

    __tablename__ = "program"

    program_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("source.source_id", ondelete="RESTRICT"))
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("category.category_id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(300))
    organizer: Mapped[str] = mapped_column(String(200))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    deadline: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10), default="DRAFT")
    extra_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    content_hash: Mapped[str] = mapped_column(CHAR(64))
    last_checked_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    source_url: Mapped[str] = mapped_column(String(500))

    source: Mapped[Source] = relationship()
    category: Mapped[Category | None] = relationship()
    applicant_types: Mapped[list["ProgramApplicantType"]] = relationship(
        back_populates="program", cascade="all, delete-orphan"
    )

    @property
    def days_left(self) -> int | None:
        """Число дней до окончания приёма — производный атрибут (FR-014).

        В базе не хранится: вычисляется на момент запроса.
        """
        if self.deadline is None:
            return None
        return (self.deadline - date.today()).days


class ProgramApplicantType(Base):
    """Типы заявителей программы — многозначный атрибут в 1НФ."""

    __tablename__ = "program_applicant_type"

    program_id: Mapped[int] = mapped_column(
        ForeignKey("program.program_id", ondelete="CASCADE"), primary_key=True
    )
    applicant_type: Mapped[str] = mapped_column(String(10), primary_key=True)

    program: Mapped[Program] = relationship(back_populates="applicant_types")


class Favorite(Base):
    """Избранные программы пользователя (M:N)."""

    __tablename__ = "favorite"

    favorite_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.user_id", ondelete="CASCADE"))
    program_id: Mapped[int] = mapped_column(ForeignKey("program.program_id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )

    user: Mapped[AppUser] = relationship(back_populates="favorites")
    program: Mapped[Program] = relationship()


class Application(Base):
    """Заявка на участие в программе, статусная модель DRAFT→PREP→SENT→RES (FR-008)."""

    __tablename__ = "application"

    application_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.user_id", ondelete="CASCADE"))
    program_id: Mapped[int] = mapped_column(ForeignKey("program.program_id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(10), default="DRAFT")
    status_date: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    result: Mapped[str | None] = mapped_column(String(10))

    user: Mapped[AppUser] = relationship(back_populates="applications")
    program: Mapped[Program] = relationship()


class ModerationQueue(Base):
    """Очередь модерации изменений программ (FR-006, FR-007)."""

    __tablename__ = "moderation_queue"

    queue_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("program.program_id", ondelete="CASCADE"))
    change_type: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(15), default="waiting")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )

    program: Mapped[Program] = relationship()


class Notification(Base):
    """Уведомление о сроке подачи или новой подходящей программе (FR-011)."""

    __tablename__ = "notification"

    notification_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.user_id", ondelete="CASCADE"))
    program_id: Mapped[int] = mapped_column(ForeignKey("program.program_id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(10))
    sent_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[AppUser] = relationship(back_populates="notifications")
    program: Mapped[Program] = relationship()


class AuditLog(Base):
    """Журнал аудита критических операций (п. 4.1.4 ТЗ, FR-015)."""

    __tablename__ = "audit_log"

    audit_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.user_id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(50))
    entity: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
