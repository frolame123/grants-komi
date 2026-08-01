"""Дата последней активности пользователя и индексы под фильтры админ-панели.

П. 4.3.1 ТЗ перечисляет «дату последней активности» среди атрибутов
пользователя, а FR-012 требует фильтровать по ней список в панели
управления. В схеме версии 2 такого поля не было.

Заодно созданы индексы по полям, по которым идёт фильтрация списка
пользователей: статус и дата регистрации. По адресу электронной почты
индекс уже есть — его создаёт ограничение уникальности.

Revision ID: 0005
Revises: 0004
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE app_user ADD COLUMN last_active_at TIMESTAMP")
    op.execute(
        "COMMENT ON COLUMN app_user.last_active_at IS "
        "'Дата и время последнего обращения к защищённым разделам; "
        "используется как фильтр в панели управления (FR-012)'"
    )
    op.execute("CREATE INDEX idx_app_user_status ON app_user (status)")
    op.execute("CREATE INDEX idx_app_user_created_at ON app_user (created_at)")
    op.execute("CREATE INDEX idx_app_user_last_active_at ON app_user (last_active_at)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_app_user_last_active_at")
    op.execute("DROP INDEX IF EXISTS idx_app_user_created_at")
    op.execute("DROP INDEX IF EXISTS idx_app_user_status")
    op.execute("ALTER TABLE app_user DROP COLUMN last_active_at")
