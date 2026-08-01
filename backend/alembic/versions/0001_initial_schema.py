"""Начальная схема БД (версия 2 даталогической модели).

DDL не дублируется в Python: миграция выполняет db/schema.sql — тот же
скрипт, что приложен к пояснительной записке и прошёл техническое ревью.
Единственный источник правды у схемы один.

Revision ID: 0001
Revises:
"""

from pathlib import Path

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA_SQL = Path(__file__).resolve().parents[2] / "db" / "schema.sql"

TABLES = [
    "audit_log",
    "notification",
    "moderation_queue",
    "application",
    "favorite",
    "program_applicant_type",
    "program",
    "category",
    "source",
    "org_profile",
    "password_reset_token",
    "email_confirmation_token",
    "app_user",
]


def upgrade() -> None:
    # Скрипт выполняется курсором драйвера напрямую. В нём есть регулярное
    # выражение со знаком «%» (проверка адреса почты) и тело функции в
    # долларовых кавычках: любой слой, который разбирает параметры запроса,
    # принимает «%» за подстановку и ломается
    cursor = op.get_bind().connection.cursor()
    cursor.execute(SCHEMA_SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS fn_anonymize_user(INTEGER)")
    for table in TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
