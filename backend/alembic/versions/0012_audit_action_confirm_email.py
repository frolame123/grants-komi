"""Действие «подтверждение почты администратором» в журнале аудита.

Администратор может вручную подтвердить почту пользователя (перевод из
pending в active) на случай недоставки письма. Событие фиксируется
отдельным действием user_confirm_email, которого перечень
chk_audit_log_action ещё не содержал.

Revision ID: 0012
Revises: 0011
"""

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

ACTIONS_BEFORE = (
    "'login', 'logout', 'password_reset', 'role_change', "
    "'program_publish', 'program_archive', 'account_delete', "
    "'register', 'rate_limit_block', 'user_block', 'user_unblock', "
    "'dict_propose', 'dict_approve', 'dict_merge', "
    "'program_create', 'program_update', 'program_reject'"
)
ACTIONS_AFTER = ACTIONS_BEFORE + ", 'user_confirm_email'"


def upgrade() -> None:
    op.execute("ALTER TABLE audit_log DROP CONSTRAINT chk_audit_log_action")
    op.execute(
        f"ALTER TABLE audit_log ADD CONSTRAINT chk_audit_log_action "
        f"CHECK (action IN ({ACTIONS_AFTER}))"
    )


def downgrade() -> None:
    # Ранее записанные подтверждения переводятся в user_unblock, иначе строки
    # не пройдут восстанавливаемое ограничение
    op.execute(
        "UPDATE audit_log SET action = 'user_unblock' "
        "WHERE action = 'user_confirm_email'"
    )
    op.execute("ALTER TABLE audit_log DROP CONSTRAINT chk_audit_log_action")
    op.execute(
        f"ALTER TABLE audit_log ADD CONSTRAINT chk_audit_log_action "
        f"CHECK (action IN ({ACTIONS_BEFORE}))"
    )
