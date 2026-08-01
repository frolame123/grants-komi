"""Схемы запросов и ответов (серверная половина двусторонней валидации).

Правила проверки хранятся рядом с описанием данных и автоматически попадают
в документацию OpenAPI.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.inn import validate_inn
from app.security import validate_password


class RegisterIn(BaseModel):
    """Форма регистрации (FR-001)."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    password_confirm: str
    pd_consent: bool = Field(description="Согласие на обработку персональных данных (152-ФЗ)")

    @field_validator("password")
    @classmethod
    def check_password(cls, value: str) -> str:
        validate_password(value)
        return value

    @model_validator(mode="after")
    def check_confirm_and_consent(self) -> "RegisterIn":
        if self.password != self.password_confirm:
            raise ValueError("Пароли не совпадают")
        if not self.pd_consent:
            raise ValueError("Без согласия на обработку персональных данных регистрация невозможна")
        return self


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class EmailIn(BaseModel):
    """Повторная отправка письма и запрос восстановления пароля."""

    email: EmailStr


class RefreshIn(BaseModel):
    refresh_token: str


class PasswordResetIn(BaseModel):
    """Смена пароля по ссылке из письма (FR-009)."""

    token: str
    password: str = Field(min_length=8, max_length=128)
    password_confirm: str

    @field_validator("password")
    @classmethod
    def check_password(cls, value: str) -> str:
        validate_password(value)
        return value

    @model_validator(mode="after")
    def check_confirm(self) -> "PasswordResetIn":
        if self.password != self.password_confirm:
            raise ValueError("Пароли не совпадают")
        return self


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    user_id: int
    email: EmailStr
    role: str
    status: str

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    detail: str


class OrgProfileIn(BaseModel):
    """Профиль организации (FR-003). Обязательны тип, ИНН и отрасль."""

    org_type: Literal["IP", "OOO", "NKO", "SMZ"]
    inn: str
    category_id: int = Field(description="Отрасль — значение справочника категорий")
    city: str = Field(min_length=2, max_length=100)
    street: str | None = Field(None, max_length=150)
    house: str | None = Field(None, max_length=20)
    org_size: Literal["micro", "small", "medium"] | None = None
    goal: str | None = Field(None, max_length=300)
    region: str = Field("Республика Коми", max_length=100)

    @model_validator(mode="after")
    def check_inn(self) -> "OrgProfileIn":
        validate_inn(self.inn, self.org_type)
        return self


class OrgProfileOut(BaseModel):
    profile_id: int
    org_type: str
    inn: str
    category_id: int | None
    city: str
    street: str | None
    house: str | None
    org_size: str | None
    goal: str | None
    region: str

    model_config = {"from_attributes": True}


class CategoryOut(BaseModel):
    category_id: int
    name: str

    model_config = {"from_attributes": True}


class ProgramOut(BaseModel):
    """Карточка программы. Число дней до срока вычисляется, а не хранится (FR-014)."""

    program_id: int
    title: str
    organizer: str
    amount: Decimal | None
    deadline: date | None
    days_left: int | None
    status: str
    category_id: int | None
    category: str | None
    source: str
    source_url: str
    applicant_types: list[str]
    regions: list[str]
    extra_json: dict
    match: int | None = Field(None, description="Степень соответствия профилю, % (FR-005)")


class UserAdminOut(BaseModel):
    """Строка списка пользователей в панели управления (FR-012)."""

    user_id: int
    email: EmailStr
    role: str
    role_name: str
    status: str
    status_name: str
    created_at: datetime
    last_active_at: datetime | None
    has_profile: bool
    deleted: bool


class UserPageOut(BaseModel):
    items: list[UserAdminOut]
    page: int
    page_size: int
    total: int


class RoleChangeIn(BaseModel):
    role: Literal["applicant", "moderator", "admin"]


class StatusChangeIn(BaseModel):
    status: Literal["active", "blocked"]


class ApplicationCreate(BaseModel):
    """Создание заявки: черновик по выбранной программе (FR-008)."""

    program_id: int
    comment: str | None = Field(None, max_length=500)


class ApplicationTransition(BaseModel):
    """Перевод заявки в следующий статус."""

    status: Literal["PREP", "SENT", "RES"]
    result: Literal["APPROVED", "REJECTED"] | None = None
    comment: str | None = Field(None, max_length=500)


class HistoryOut(BaseModel):
    status: str
    status_name: str
    comment: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApplicationOut(BaseModel):
    application_id: int
    program_id: int
    program_title: str
    status: str
    status_name: str
    status_date: date
    result: str | None
    comment: str | None
    program_archived: bool = Field(description="Признак «программа завершена» (п. 4.2.8 ТЗ)")
    history: list[HistoryOut]


class PageOut(BaseModel):
    """Страница выдачи каталога и подбора."""

    items: list[ProgramOut]
    page: int
    page_size: int
    total: int
