"""История переходов заявки, комментарий заявителя и повторная подача.

Схема версии 2 расходилась с п. 4.2.8 и п. 4.3.1 ТЗ в трёх местах:

  * ограничение uniq_application_user_id_program_id запрещало вторую заявку
    на ту же программу навсегда, тогда как ТЗ разрешает подать заново после
    отказа: уникальность распространяется только на активные заявки.
    Заменено частичным уникальным индексом с условием status <> 'RES';
  * отсутствовала колонка под комментарий заявителя (до 500 символов);
  * отсутствовала история переходов, хотя п. 4.3.1 перечисляет её в составе
    сущности «Заявка»: статус, дата, инициатор.

Revision ID: 0004
Revises: 0003
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE application ADD COLUMN comment VARCHAR(500)")
    op.execute(
        "COMMENT ON COLUMN application.comment IS "
        "'Необязательный комментарий заявителя к заявке, до 500 символов (FR-008)'"
    )

    # Уникальность — только для активных заявок: после внесения результата
    # заявитель вправе подать новую заявку на ту же программу
    op.execute("ALTER TABLE application DROP CONSTRAINT uniq_application_user_id_program_id")
    op.execute(
        "CREATE UNIQUE INDEX uniq_application_active ON application (user_id, program_id) "
        "WHERE status <> 'RES'"
    )

    op.execute(
        """
        CREATE TABLE application_history (
            history_id      SERIAL      NOT NULL,
            application_id  INTEGER     NOT NULL,
            status          VARCHAR(10) NOT NULL,
            comment         VARCHAR(500),
            initiator_id    INTEGER,
            created_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT pk_application_history PRIMARY KEY (history_id),
            CONSTRAINT fk_application_history_application_id FOREIGN KEY (application_id)
                REFERENCES application (application_id) ON DELETE CASCADE,
            CONSTRAINT fk_application_history_initiator_id FOREIGN KEY (initiator_id)
                REFERENCES app_user (user_id) ON DELETE SET NULL,
            CONSTRAINT chk_application_history_status
                CHECK (status IN ('DRAFT', 'PREP', 'SENT', 'RES'))
        )
        """
    )
    op.execute(
        "COMMENT ON TABLE application_history IS "
        "'История переходов заявки: статус, дата, инициатор, комментарий на момент "
        "перехода (FR-008, п. 4.3.1 ТЗ)'"
    )
    op.execute(
        "CREATE INDEX idx_application_history_application_id "
        "ON application_history (application_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS application_history CASCADE")
    op.execute("DROP INDEX IF EXISTS uniq_application_active")
    op.execute(
        "ALTER TABLE application ADD CONSTRAINT uniq_application_user_id_program_id "
        "UNIQUE (user_id, program_id)"
    )
    op.execute("ALTER TABLE application DROP COLUMN comment")
