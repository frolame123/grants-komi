"""Самопроверка сводной статистики панели администратора.

Проверка идёт против живой базы: смысл счётчиков и графиков в том, что они
согласованы между собой и с содержимым таблиц, а это можно увидеть только на
настоящих данных.

Требуется наполненная база: alembic upgrade head и заливка db/seed.sql.

Запуск:  python check_stats.py
"""

from datetime import date, timedelta

from sqlalchemy import func, select

from app.api.stats import (
    PROGRAM_STATUS_NAMES,
    counters,
    grouped,
    registrations_by_day,
    sources_status,
)
from app.db import SessionLocal
from app.models import Application, AppUser, Program, Source
from app.workflow import STATUS_NAMES as APPLICATION_STATUS_NAMES


def check_counters_consistency() -> None:
    """Счётчики не должны противоречить друг другу."""
    with SessionLocal() as db:
        data = counters(db)

        assert data.users_active <= data.users_total, "активных не может быть больше всех"
        assert data.users_new_month <= data.users_total, (
            "новых за месяц не может быть больше общего числа: "
            "условие о неудалённых записях должно повторяться во всех счётчиках"
        )
        assert data.programs_published <= data.programs_total
        assert data.applications_active <= data.applications_total
        assert all(value >= 0 for value in data.model_dump().values())


def check_counters_match_tables() -> None:
    """Счётчики совпадают с прямым подсчётом в таблицах."""
    with SessionLocal() as db:
        data = counters(db)

        published = db.scalar(
            select(func.count()).select_from(Program).where(Program.status == "PUB")
        )
        assert data.programs_published == published

        active = db.scalar(
            select(func.count()).select_from(Application).where(Application.status != "RES")
        )
        assert data.applications_active == active


def check_series_completeness() -> None:
    """График регистраций не имеет разрывов: дни без событий тоже присутствуют."""
    with SessionLocal() as db:
        series = registrations_by_day(db, 14)

    assert len(series) == 14, "в графике должно быть ровно столько точек, сколько дней"
    expected = [
        (date.today() - timedelta(days=13 - offset)).strftime("%d.%m") for offset in range(14)
    ]
    assert [point.label for point in series] == expected, "дни идут подряд и по порядку"


def check_groupings() -> None:
    """Распределения содержат все значения классификатора, включая нулевые."""
    with SessionLocal() as db:
        programs = grouped(db, Program.status, PROGRAM_STATUS_NAMES)
        applications = grouped(db, Application.status, APPLICATION_STATUS_NAMES)
        total_programs = db.scalar(select(func.count()).select_from(Program))

    assert len(programs) == len(PROGRAM_STATUS_NAMES), "все статусы программ на графике"
    assert len(applications) == len(APPLICATION_STATUS_NAMES), "все статусы заявок"
    assert sum(point.value for point in programs) == total_programs, (
        "сумма по статусам обязана совпадать с общим числом программ"
    )


def check_sources() -> None:
    """Состояние источников показывается по всем, включая ни разу не опрошенные."""
    with SessionLocal() as db:
        rows = sources_status(db)
        total = db.scalar(select(func.count()).select_from(Source))

    assert len(rows) == total, "в сводке должны быть все источники из перечня"
    assert all(row.source_name for row in rows)


def main() -> None:
    for check in (
        check_counters_consistency,
        check_counters_match_tables,
        check_series_completeness,
        check_groupings,
        check_sources,
    ):
        check()
        print(f"OK: {check.__name__}")


if __name__ == "__main__":
    main()
