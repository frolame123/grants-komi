"""Отчёт о планах выполнения типовых запросов каталога.

Проверяет, что созданные индексы действительно используются. На нескольких
строках PostgreSQL всегда предпочтёт последовательное чтение — это дешевле
любого индекса, поэтому таблица предварительно наполняется до объёма, при
котором выбор планировщика становится осмысленным.

Синтетические программы помечены источником «Нагрузочные данные» и удаляются
повторной заливкой db/seed.sql.

Запуск:  python db/explain_report.py [число_программ]
"""

import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text  # noqa: E402

from app.config import settings  # noqa: E402

DEFAULT_VOLUME = 20_000

QUERIES = {
    "Каталог: опубликованные программы по возрастанию срока (FR-004)": (
        """
        SELECT program_id, title, deadline FROM program
        WHERE status = 'PUB' ORDER BY deadline LIMIT 20
        """,
        "ожидается индекс по сроку подачи",
    ),
    "Каталог с фильтром по категории (FR-004)": (
        """
        SELECT program_id, title FROM program
        WHERE status = 'PUB' AND category_id = 1 ORDER BY deadline LIMIT 20
        """,
        "ожидается индекс по сроку подачи, категория отсеивается фильтром",
    ),
    "Выборочное условие в JSONB, GIN-индекс (п. 4.3.1 ТЗ)": (
        """
        SELECT program_id FROM program WHERE extra_json @> '{"priority": "особая"}'
        """,
        "ожидается GIN-индекс: условию удовлетворяет доля процента строк",
    ),
    "Частое условие в JSONB — индекс намеренно не применяется": (
        """
        SELECT program_id FROM program WHERE extra_json @> '{"co_financing": "20%"}'
        """,
        "ожидается последовательное чтение: под условие подходит около 15 % "
        "таблицы, и обращаться к индексу дороже, чем прочитать её целиком",
    ),
    "Поиск программы по ссылке первоисточника (FR-006)": (
        """
        SELECT program_id FROM program
        WHERE source_id = 1 AND source_url = 'https://example.org/programs/777'
        """,
        "ожидается индекс уникальности пары «источник, ссылка»",
    ),
}


def fill(connection, volume: int) -> None:
    """Наполнение таблицы программ синтетическими записями."""
    source_id = connection.execute(
        text("SELECT source_id FROM source ORDER BY source_id LIMIT 1")
    ).scalar()
    categories = [
        row[0] for row in connection.execute(text("SELECT category_id FROM category"))
    ]
    if source_id is None or not categories:
        raise SystemExit("Сначала залейте db/seed.sql: нужны источники и категории")

    existing = connection.execute(
        text("SELECT count(*) FROM program WHERE organizer = 'Нагрузочные данные'")
    ).scalar()
    if existing >= volume:
        print(f"Синтетических записей уже {existing}, наполнение пропущено")
        return

    print(f"Добавляю {volume - existing} записей...")
    rows = []
    for number in range(existing, volume):
        rows.append(
            {
                "source_id": source_id,
                "category_id": random.choice(categories),
                "title": f"Программа поддержки № {number}",
                "amount": random.randrange(50_000, 5_000_000, 50_000),
                "deadline": date.today() + timedelta(days=random.randint(-200, 400)),
                "status": random.choice(["PUB", "PUB", "PUB", "MOD", "ARCH"]),
                "hash": f"{number:064d}",
                "url": f"https://example.org/programs/{number}",
                # Частое условие для одного запроса и редкое для другого:
                # план зависит от доли подходящих строк, и отчёт показывает оба случая
                "extra": (
                    '{"priority": "особая"}'
                    if number % 500 == 0
                    else ('{"co_financing": "20%"}' if number % 7 == 0 else "{}")
                ),
            }
        )
    connection.execute(
        text(
            """
            INSERT INTO program (source_id, category_id, title, organizer, amount,
                                 deadline, status, extra_json, content_hash, source_url)
            VALUES (:source_id, :category_id, :title, 'Нагрузочные данные', :amount,
                    :deadline, :status, CAST(:extra AS jsonb), :hash, :url)
            """
        ),
        rows,
    )
    connection.execute(text("ANALYZE program"))


def report(connection) -> None:
    for title, (query, expectation) in QUERIES.items():
        print("\n" + "=" * 78)
        print(title)
        print("Ожидание:", expectation)
        print("=" * 78)
        plan = connection.execute(text("EXPLAIN ANALYZE " + query))
        used_index = False
        for (line,) in plan:
            print(" ", line)
            if "Index" in line or "Bitmap" in line:
                used_index = True
        print("  →", "индекс используется" if used_index else "последовательное чтение")


def main() -> None:
    volume = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_VOLUME
    engine = create_engine(settings.database_url)
    with engine.begin() as connection:
        fill(connection, volume)
        total = connection.execute(text("SELECT count(*) FROM program")).scalar()
        print(f"Всего программ в таблице: {total}")
        report(connection)


if __name__ == "__main__":
    main()
