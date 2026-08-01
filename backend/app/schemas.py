"""Схемы запросов и ответов (серверная половина двусторонней валидации).

Правила проверки хранятся рядом с описанием данных и автоматически попадают
в документацию OpenAPI.
"""

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

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
