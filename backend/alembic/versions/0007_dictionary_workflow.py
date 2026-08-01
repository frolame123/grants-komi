"""Регламент ведения справочников: предложение, утверждение, объединение.

П. 4.2.16 ТЗ описывает для справочников порядок, которого схема версии 2 не
поддерживала: новое значение предлагает контент-менеджер, в силу оно
вступает после утверждения администратором, а удаление значений не
допускается — вместо него выполняется объединение с существующим значением с
переносом всех ссылок.

Для этого справочнику нужны три атрибута:

  * status — состояние значения: предложено, утверждено, объединено;
  * proposed_by — кто предложил, для журнала и разбора спорных случаев;
  * merged_into_id — куда объединено; ссылка на само себя в той же таблице.

Строка объединённого значения сохраняется: физическое удаление запрещено ТЗ,
а ссылка merged_into_id позволяет проследить, во что превратился дубль.

Существующие значения помечаются утверждёнными: они внесены при развёртывании
и в утверждении не нуждаются.

Revision ID: 0007
Revises: 0006
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

ACTIONS_BEFORE = (
    "'login', 'logout', 'password_reset', 'role_change', "
    "'program_publish', 'program_archive', 'account_delete', "
    "'register', 'rate_limit_block', 'user_block', 'user_unblock'"
)
ACTIONS_AFTER = ACTIONS_BEFORE + ", 'dict_propose', 'dict_approve', 'dict_merge'"


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE category
            ADD COLUMN status         VARCHAR(10) NOT NULL DEFAULT 'approved',
            ADD COLUMN proposed_by    INTEGER,
            ADD COLUMN merged_into_id INTEGER,
            ADD COLUMN created_at     TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
            ADD CONSTRAINT fk_category_proposed_by FOREIGN KEY (proposed_by)
                REFERENCES app_user (user_id) ON DELETE SET NULL,
            ADD CONSTRAINT fk_category_merged_into_id FOREIGN KEY (merged_into_id)
                REFERENCES category (category_id) ON DELETE RESTRICT,
            ADD CONSTRAINT chk_category_status
                CHECK (status IN ('proposed', 'approved', 'merged')),
            ADD CONSTRAINT chk_category_merged CHECK (
                (status = 'merged' AND merged_into_id IS NOT NULL)
                OR (status <> 'merged' AND merged_into_id IS NULL)
            ),
            ADD CONSTRAINT chk_category_not_self_merged
                CHECK (merged_into_id IS NULL OR merged_into_id <> category_id)
        """
    )
    op.execute(
        "COMMENT ON COLUMN category.status IS "
        "'Состояние значения справочника: proposed — предложено контент-менеджером, "
        "approved — утверждено администратором, merged — объединено с другим (FR-016)'"
    )
    op.execute(
        "COMMENT ON COLUMN category.merged_into_id IS "
        "'Значение, с которым объединён дубль; строка сохраняется, так как удаление "
        "значений справочника не допускается (п. 4.2.16 ТЗ)'"
    )
    op.execute("CREATE INDEX idx_category_status ON category (status)")

    op.execute("ALTER TABLE audit_log DROP CONSTRAINT chk_audit_log_action")
    op.execute(
        f"ALTER TABLE audit_log ADD CONSTRAINT chk_audit_log_action "
        f"CHECK (action IN ({ACTIONS_AFTER}))"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE audit_log SET action = 'role_change' "
        "WHERE action IN ('dict_propose', 'dict_approve', 'dict_merge')"
    )
    op.execute("ALTER TABLE audit_log DROP CONSTRAINT chk_audit_log_action")
    op.execute(
        f"ALTER TABLE audit_log ADD CONSTRAINT chk_audit_log_action "
        f"CHECK (action IN ({ACTIONS_BEFORE}))"
    )

    op.execute("DROP INDEX IF EXISTS idx_category_status")
    op.execute(
        """
        ALTER TABLE category
            DROP CONSTRAINT chk_category_not_self_merged,
            DROP CONSTRAINT chk_category_merged,
            DROP CONSTRAINT chk_category_status,
            DROP CONSTRAINT fk_category_merged_into_id,
            DROP CONSTRAINT fk_category_proposed_by,
            DROP COLUMN created_at,
            DROP COLUMN merged_into_id,
            DROP COLUMN proposed_by,
            DROP COLUMN status
        """
    )
