"""Отправка писем: подтверждение адреса (FR-002) и восстановление пароля (FR-009).

Если SMTP не настроен, письмо печатается в журнал приложения — этого
достаточно для разработки и демонстрации, ссылку видно в логах контейнера.
"""

import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

log = logging.getLogger(__name__)


def send_email(to: str, subject: str, body: str) -> None:
    if not settings.smtp_host:
        log.warning("SMTP не настроен, письмо не отправлено.\nКому: %s\n%s\n\n%s", to, subject, body)
        return

    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(message)


def send_confirmation(to: str, token: str) -> None:
    link = f"{settings.public_url}/confirm?token={token}"
    send_email(
        to,
        "Подтверждение адреса — Гранты Коми",
        f"Для завершения регистрации перейдите по ссылке (действует 24 часа):\n{link}",
    )


def send_password_reset(to: str, token: str) -> None:
    link = f"{settings.public_url}/reset-password?token={token}"
    send_email(
        to,
        "Восстановление пароля — Гранты Коми",
        f"Для смены пароля перейдите по ссылке (действует 1 час):\n{link}\n\n"
        "Если вы не запрашивали смену пароля, письмо можно проигнорировать.",
    )
