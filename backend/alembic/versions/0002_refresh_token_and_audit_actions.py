"""Отзыв токенов обновления и расширение перечня действий журнала аудита.

Схема версии 2 не покрывала два требования ТЗ:
  * FR-010 — выход из системы отзывает refresh-токен на сервере, для чего
    нужен перечень выданных токенов;
  * п. 4.1.4 — в журнал аудита пишутся регистрация и блокировки по
    ограничению частоты запросов, но ограничение chk_audit_log_action таких
    значений не допускало.

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

ACTIONS_V2 = (
    "'login', 'logout', 'password_reset', 'role_change', "
    "'program_publish', 'program_archive', 'account_delete'"
)
ACTIONS_V3 = ACTIONS_V2 + ", 'register', 'rate_limit_block'"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE refresh_token (
            token_id    SERIAL      NOT NULL,
            user_id     INTEGER     NOT NULL,
            jti         VARCHAR(64) NOT NULL,
            expires_at  TIMESTAMP   NOT NULL,
            revoked     BOOLEAN     NOT NULL DEFAULT FALSE,
            created_at  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT pk_refresh_token PRIMARY KEY (token_id),
            CONSTRAINT fk_refresh_token_user_id FOREIGN KEY (user_id)
                REFERENCES app_user (user_id) ON DELETE CASCADE,
            CONSTRAINT uniq_refresh_token_jti UNIQUE (jti)
        )
        """
    )
    op.execute(
        "COMMENT ON TABLE refresh_token IS "
        "'Выданные токены обновления; отозванные отмечаются флагом revoked (FR-010)'"
    )
    op.execute("CREATE INDEX idx_refresh_token_user_id ON refresh_token (user_id)")

    op.execute("ALTER TABLE audit_log DROP CONSTRAINT chk_audit_log_action")
    op.execute(
        f"ALTER TABLE audit_log ADD CONSTRAINT chk_audit_log_action "
        f"CHECK (action IN ({ACTIONS_V3}))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE audit_log DROP CONSTRAINT chk_audit_log_action")
    op.execute(
        f"ALTER TABLE audit_log ADD CONSTRAINT chk_audit_log_action "
        f"CHECK (action IN ({ACTIONS_V2}))"
    )
    op.execute("DROP TABLE IF EXISTS refresh_token CASCADE")
