"""Причина отклонения, снимок прежнего состояния и правило схлопывания очереди.

Схема версии 2 описывала очередь модерации четырьмя полями, тогда как
FR-007 и п. 4.3.1 ТЗ требуют большего:

  * причина отклонения (до 300 символов) — п. 4.3.1 перечисляет её в составе
    сущности, а FR-007 делает обязательной при отклонении;
  * представление «было / стало» для изменений — без снимка прежнего
    состояния карточки контент-менеджеру нечего сравнивать;
  * запись о том, кто и когда рассмотрел — причина отклонения по ТЗ доступна
    администратору, и без автора она бесполезна.

Дополнительно правило «несколько изменений одной программы схлопываются в
одну запись очереди» вынесено на уровень базы частичным уникальным индексом:
у программы не может быть двух записей в состоянии ожидания. Это правило
слишком легко нарушить со стороны парсера, чтобы полагаться только на код.

Revision ID: 0008
Revises: 0007
"""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

ACTIONS_BEFORE = (
    "'login', 'logout', 'password_reset', 'role_change', "
    "'program_publish', 'program_archive', 'account_delete', "
    "'register', 'rate_limit_block', 'user_block', 'user_unblock', "
    "'dict_propose', 'dict_approve', 'dict_merge'"
)
ACTIONS_AFTER = ACTIONS_BEFORE + ", 'program_create', 'program_update', 'program_reject'"


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE moderation_queue
            ADD COLUMN reason        VARCHAR(300),
            ADD COLUMN prev_snapshot JSONB,
            ADD COLUMN resolved_at   TIMESTAMP,
            ADD COLUMN resolved_by   INTEGER,
            ADD CONSTRAINT fk_moderation_queue_resolved_by FOREIGN KEY (resolved_by)
                REFERENCES app_user (user_id) ON DELETE SET NULL,
            ADD CONSTRAINT chk_moderation_queue_reason CHECK (
                status <> 'rejected' OR reason IS NOT NULL
            )
        """
    )
    op.execute(
        "COMMENT ON COLUMN moderation_queue.reason IS "
        "'Причина отклонения, до 300 символов; обязательна при status = rejected (FR-007)'"
    )
    op.execute(
        "COMMENT ON COLUMN moderation_queue.prev_snapshot IS "
        "'Снимок карточки до изменения; источник представления «было / стало» "
        "для записей типа UPD (FR-007)'"
    )
    op.execute(
        "CREATE UNIQUE INDEX uniq_moderation_queue_waiting ON moderation_queue (program_id) "
        "WHERE status = 'waiting'"
    )
    op.execute(
        "CREATE INDEX idx_moderation_queue_created_at ON moderation_queue (created_at)"
    )

    op.execute("ALTER TABLE audit_log DROP CONSTRAINT chk_audit_log_action")
    op.execute(
        f"ALTER TABLE audit_log ADD CONSTRAINT chk_audit_log_action "
        f"CHECK (action IN ({ACTIONS_AFTER}))"
    )

    # FR-007 требует фиксировать прямую правку карточки «с указанием полей»,
    # а в журнале аудита не было места под подробности события
    op.execute("ALTER TABLE audit_log ADD COLUMN details VARCHAR(500)")
    op.execute(
        "COMMENT ON COLUMN audit_log.details IS "
        "'Подробности события: перечень изменённых полей, идентификатор "
        "значения при объединении справочника и подобное'"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE audit_log DROP COLUMN details")
    op.execute(
        "UPDATE audit_log SET action = 'program_publish' "
        "WHERE action IN ('program_create', 'program_update', 'program_reject')"
    )
    op.execute("ALTER TABLE audit_log DROP CONSTRAINT chk_audit_log_action")
    op.execute(
        f"ALTER TABLE audit_log ADD CONSTRAINT chk_audit_log_action "
        f"CHECK (action IN ({ACTIONS_BEFORE}))"
    )

    op.execute("DROP INDEX IF EXISTS idx_moderation_queue_created_at")
    op.execute("DROP INDEX IF EXISTS uniq_moderation_queue_waiting")
    op.execute(
        """
        ALTER TABLE moderation_queue
            DROP CONSTRAINT chk_moderation_queue_reason,
            DROP CONSTRAINT fk_moderation_queue_resolved_by,
            DROP COLUMN resolved_by,
            DROP COLUMN resolved_at,
            DROP COLUMN prev_snapshot,
            DROP COLUMN reason
        """
    )
