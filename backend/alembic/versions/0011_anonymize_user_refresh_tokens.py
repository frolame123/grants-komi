"""Обезличивание учётной записи удаляет и токены обновления.

Функция fn_anonymize_user написана в схеме версии 2 и перечисляет таблицы
поимённо. Таблица refresh_token появилась позже, миграцией 0002, и в функцию
не попала: после удаления учётной записи выданные ей токены обновления
оставались в базе.

Практического доступа они не давали — учётная запись помечается
заблокированной, и проверка прав отклоняет запрос независимо от токена. Но
записи, связывающие человека с его сеансами, обязаны исчезать вместе с
остальными данными (152-ФЗ, FR-013).

Revision ID: 0011
Revises: 0010
"""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

BODY_WITH_TOKENS = """
    DELETE FROM favorite WHERE user_id = p_user_id;
    DELETE FROM notification WHERE user_id = p_user_id;
    DELETE FROM application WHERE user_id = p_user_id;
    DELETE FROM org_profile WHERE user_id = p_user_id;
    DELETE FROM email_confirmation_token WHERE user_id = p_user_id;
    DELETE FROM password_reset_token WHERE user_id = p_user_id;
    DELETE FROM refresh_token WHERE user_id = p_user_id;
"""

BODY_WITHOUT_TOKENS = """
    DELETE FROM favorite WHERE user_id = p_user_id;
    DELETE FROM notification WHERE user_id = p_user_id;
    DELETE FROM application WHERE user_id = p_user_id;
    DELETE FROM org_profile WHERE user_id = p_user_id;
    DELETE FROM email_confirmation_token WHERE user_id = p_user_id;
    DELETE FROM password_reset_token WHERE user_id = p_user_id;
"""

TEMPLATE = """
CREATE OR REPLACE FUNCTION fn_anonymize_user(p_user_id INTEGER)
RETURNS VOID AS $$
BEGIN
{body}
    UPDATE app_user
    SET email         = 'deleted-' || p_user_id || '@anonymized.local',
        password_hash = '$deleted$',
        status        = 'blocked',
        deleted_at    = CURRENT_TIMESTAMP
    WHERE user_id = p_user_id;

    INSERT INTO audit_log (user_id, action, entity, entity_id)
    VALUES (p_user_id, 'account_delete', 'app_user', p_user_id);
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.get_bind().connection.cursor().execute(TEMPLATE.format(body=BODY_WITH_TOKENS))


def downgrade() -> None:
    op.get_bind().connection.cursor().execute(TEMPLATE.format(body=BODY_WITHOUT_TOKENS))
