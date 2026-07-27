"""Самопроверка: модели SQLAlchemy не разошлись со схемой db/schema.sql.

Схема — источник правды, модели её отражают. Проверка не требует запущенной
СУБД: сравниваются имена таблиц и колонок, разобранные из DDL, с метаданными.

Запуск:  python check_models.py
"""

import re
from pathlib import Path

from app.db import Base
from app import models  # noqa: F401  — регистрация моделей в метаданных

SCHEMA_SQL = Path(__file__).resolve().parent / "db" / "schema.sql"

# Таблицы, добавленные миграциями после версии 2 схемы: их нет в schema.sql
# (он — снимок сданной и прошедшей ревью версии), проверяются отдельно.
POST_V2_TABLES = {"refresh_token": "0002"}

CREATE_TABLE = re.compile(r"CREATE TABLE (\w+) \((.*?)\n\);", re.S)
# Колонка — строка с отступом ровно 4 пробела, имя в нижнем регистре, далее тип.
# Ограничения (CONSTRAINT/CHECK/OR) и продолжения строк под это не подходят.
COLUMN_LINE = re.compile(r"^ {4}([a-z_]+)\s+[A-Z]")


def parse_schema() -> dict[str, set[str]]:
    """Имена таблиц и колонок из DDL."""
    sql = SCHEMA_SQL.read_text(encoding="utf-8")
    tables: dict[str, set[str]] = {}
    for name, body in CREATE_TABLE.findall(sql):
        tables[name] = {
            m.group(1) for line in body.splitlines() if (m := COLUMN_LINE.match(line))
        }
    return tables


def main() -> None:
    schema = parse_schema()
    assert schema, "не удалось разобрать schema.sql — проверьте формат DDL"

    orm = {t.name: {c.name for c in t.columns} for t in Base.metadata.tables.values()}

    only_in_schema = set(schema) - set(orm)
    only_in_orm = set(orm) - set(schema) - set(POST_V2_TABLES)
    assert not only_in_schema, f"таблицы есть в schema.sql, но нет моделей: {only_in_schema}"
    assert not only_in_orm, (
        f"модели есть, но нет ни в schema.sql, ни в списке добавленных "
        f"миграциями: {only_in_orm}"
    )

    for table, columns in schema.items():
        assert orm[table] == columns, (
            f"таблица {table}: расхождение колонок; "
            f"нет в модели: {columns - orm[table]}, лишние в модели: {orm[table] - columns}"
        )

    print(f"OK: {len(schema)} таблиц, {sum(len(c) for c in schema.values())} колонок совпадают")


if __name__ == "__main__":
    main()
