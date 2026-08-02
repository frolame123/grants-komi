"""Лог прогонов модуля агрегации.

П. 4.2.6 ТЗ требует фиксировать каждый запуск парсера: источник, время
начала и окончания, число новых, изменённых и архивированных записей, число
ошибок; лог доступен администратору. В схеме версии 2 такой сущности не было
вовсе — модуль агрегации проектировался, но не документировался в модели
данных.

Состояние прогона реализовано перечислимым типом PostgreSQL, а не
ограничением CHECK. Это единственное место в проекте, где применён ENUM, и
выбрано оно осознанно: перечень состояний прогона задан алгоритмом обработки
и меняться не может, тогда как статусы программ и заявок принадлежат
предметной области и в развитии системы дополняются.

Состояния:
  success   — прогон завершён, изменения применены;
  failed    — источник недоступен после трёх повторных попыток;
  discarded — результат отброшен целиком: разбор вернул ноль карточек либо
              более половины карточек с незаполненными обязательными полями,
              что означает вероятное изменение вёрстки источника.

Revision ID: 0009
Revises: 0008
"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE TYPE parser_run_status AS ENUM ('success', 'failed', 'discarded')")
    op.execute(
        """
        CREATE TABLE parser_run (
            run_id          SERIAL            NOT NULL,
            source_id       INTEGER           NOT NULL,
            started_at      TIMESTAMP         NOT NULL DEFAULT CURRENT_TIMESTAMP,
            finished_at     TIMESTAMP,
            status          parser_run_status NOT NULL,
            new_count       INTEGER           NOT NULL DEFAULT 0,
            updated_count   INTEGER           NOT NULL DEFAULT 0,
            archived_count  INTEGER           NOT NULL DEFAULT 0,
            error_count     INTEGER           NOT NULL DEFAULT 0,
            message         VARCHAR(500),
            CONSTRAINT pk_parser_run PRIMARY KEY (run_id),
            CONSTRAINT fk_parser_run_source_id FOREIGN KEY (source_id)
                REFERENCES source (source_id) ON DELETE CASCADE,
            CONSTRAINT chk_parser_run_counts CHECK (
                new_count >= 0 AND updated_count >= 0
                AND archived_count >= 0 AND error_count >= 0
            )
        )
        """
    )
    op.execute(
        "COMMENT ON TABLE parser_run IS "
        "'Лог прогонов модуля агрегации: источник, время, счётчики изменений (FR-006)'"
    )
    op.execute(
        "COMMENT ON COLUMN parser_run.status IS "
        "'Итог прогона: success — применён, failed — источник недоступен, "
        "discarded — результат отброшен из-за вероятного изменения вёрстки'"
    )
    op.execute(
        "COMMENT ON COLUMN parser_run.message IS "
        "'Пояснение к неуспешному прогону, попадает в уведомление администратору'"
    )
    op.execute("CREATE INDEX idx_parser_run_source_id ON parser_run (source_id)")
    op.execute("CREATE INDEX idx_parser_run_started_at ON parser_run (started_at)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS parser_run CASCADE")
    op.execute("DROP TYPE IF EXISTS parser_run_status")
