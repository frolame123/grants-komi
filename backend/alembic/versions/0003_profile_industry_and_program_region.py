"""Отрасль профиля и регионы действия программы.

Схема версии 2 не содержала двух атрибутов, без которых подбор (FR-005)
неработоспособен:
  * отрасль организации — FR-003 объявляет её обязательным полем профиля,
    FR-005 начисляет за совпадение 40 баллов;
  * регионы действия программы — п. 4.3.1 ТЗ описывает их как многозначный
    атрибут, FR-005 начисляет за совпадение 30 баллов.

Отдельный справочник отраслей не заводится: программы уже классифицируются
справочником category, и отрасль профиля ссылается на него же — совпадение
проверяется сравнением идентификаторов без сопоставления наименований.

Regions — многозначный атрибут, вынесен в отдельное отношение по образцу
program_applicant_type (1НФ).

Revision ID: 0003
Revises: 0002
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE org_profile
            ADD COLUMN category_id INTEGER,
            ADD CONSTRAINT fk_org_profile_category_id FOREIGN KEY (category_id)
                REFERENCES category (category_id) ON DELETE SET NULL
        """
    )
    op.execute(
        "COMMENT ON COLUMN org_profile.category_id IS "
        "'Отрасль деятельности организации; ссылается на справочник категорий, "
        "которым классифицируются программы (FR-003, FR-005)'"
    )
    op.execute("CREATE INDEX idx_org_profile_category_id ON org_profile (category_id)")

    op.execute(
        """
        CREATE TABLE program_region (
            program_id  INTEGER      NOT NULL,
            region      VARCHAR(100) NOT NULL,
            CONSTRAINT pk_program_region PRIMARY KEY (program_id, region),
            CONSTRAINT fk_program_region_program_id FOREIGN KEY (program_id)
                REFERENCES program (program_id) ON DELETE CASCADE
        )
        """
    )
    op.execute(
        "COMMENT ON TABLE program_region IS "
        "'Регионы действия программы (многозначный атрибут сущности PROGRAM, 1НФ)'"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS program_region CASCADE")
    op.execute("DROP INDEX IF EXISTS idx_org_profile_category_id")
    op.execute("ALTER TABLE org_profile DROP CONSTRAINT fk_org_profile_category_id")
    op.execute("ALTER TABLE org_profile DROP COLUMN category_id")
