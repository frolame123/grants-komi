"""Действия блокировки в перечне журнала аудита.

Блокировка и разблокировка учётной записи (FR-012) записывались действием
role_change, поскольку ограничение chk_audit_log_action подходящего значения
не содержало. Запись при этом велась, но в журнале блокировку невозможно было
отличить от смены роли, а п. 4.1.4 ТЗ требует различать эти события.

Revision ID: 0006
Revises: 0005
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

ACTIONS_BEFORE = (
    "'login', 'logout', 'password_reset', 'role_change', "
    "'program_publish', 'program_archive', 'account_delete', "
    "'register', 'rate_limit_block'"
)
ACTIONS_AFTER = ACTIONS_BEFORE + ", 'user_block', 'user_unblock'"


def upgrade() -> None:
    op.execute("ALTER TABLE audit_log DROP CONSTRAINT chk_audit_log_action")
    op.execute(
        f"ALTER TABLE audit_log ADD CONSTRAINT chk_audit_log_action "
        f"CHECK (action IN ({ACTIONS_AFTER}))"
    )


def downgrade() -> None:
    # Ранее записанные блокировки переводятся в role_change, иначе строки
    # не пройдут восстанавливаемое ограничение
    op.execute(
        "UPDATE audit_log SET action = 'role_change' "
        "WHERE action IN ('user_block', 'user_unblock')"
    )
    op.execute("ALTER TABLE audit_log DROP CONSTRAINT chk_audit_log_action")
    op.execute(
        f"ALTER TABLE audit_log ADD CONSTRAINT chk_audit_log_action "
        f"CHECK (action IN ({ACTIONS_BEFORE}))"
    )
