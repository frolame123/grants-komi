"""Сводная статистика для панели администратора.

Данные для счётчиков и графиков собираются агрегирующими запросами к базе, а
не вычитыванием записей в память: на графике за месяц может стоять любое
число регистраций, и переносить их в приложение только ради подсчёта
бессмысленно.
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db import get_db
from app.models import (
    Application,
    AppUser,
    ModerationQueue,
    Notification,
    ParserRun,
    Program,
    Source,
)
from app.rbac import ROLE_NAMES
from app.schemas import DashboardOut, SeriesPointOut, SourceStatusOut, StatsCountersOut
from app.workflow import STATUS_NAMES as APPLICATION_STATUS_NAMES

router = APIRouter(prefix="/api/admin/stats", tags=["Статистика"])

PROGRAM_STATUS_NAMES = {
    "DRAFT": "Черновик",
    "MOD": "На модерации",
    "PUB": "Опубликована",
    "ARCH": "Архив",
}

DEFAULT_PERIOD_DAYS = 30


def counters(db: Session) -> StatsCountersOut:
    """Счётчики верхнего ряда панели."""
    total = lambda model, *conditions: (  # noqa: E731 — короткий локальный помощник
        db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0
    )
    month_ago = date.today() - timedelta(days=DEFAULT_PERIOD_DAYS)

    return StatsCountersOut(
        users_total=total(AppUser, AppUser.deleted_at.is_(None)),
        users_active=total(AppUser, AppUser.status == "active", AppUser.deleted_at.is_(None)),
        # Условие о неудалённых обязано повторяться во всех счётчиках
        # пользователей: иначе «новых за месяц» окажется больше, чем «всего»
        users_new_month=total(
            AppUser, AppUser.created_at >= month_ago, AppUser.deleted_at.is_(None)
        ),
        programs_published=total(Program, Program.status == "PUB"),
        programs_total=total(Program),
        applications_total=total(Application),
        applications_active=total(Application, Application.status != "RES"),
        moderation_waiting=total(ModerationQueue, ModerationQueue.status == "waiting"),
        notifications_unread=total(Notification, Notification.is_read.is_(False)),
    )


def registrations_by_day(db: Session, days: int) -> list[SeriesPointOut]:
    """Регистрации по дням за период.

    Дни без регистраций в результат запроса не попадают — их достраивает
    приложение, иначе на графике образуются разрывы.
    """
    since = date.today() - timedelta(days=days - 1)
    rows = db.execute(
        select(func.date(AppUser.created_at).label("day"), func.count())
        .where(AppUser.created_at >= since)
        .group_by("day")
    ).all()
    counts = {row[0]: row[1] for row in rows}

    return [
        SeriesPointOut(
            label=(since + timedelta(days=offset)).strftime("%d.%m"),
            value=counts.get(since + timedelta(days=offset), 0),
        )
        for offset in range(days)
    ]


def grouped(db: Session, column, names: dict[str, str]) -> list[SeriesPointOut]:
    """Распределение записей по значению столбца с русскими подписями."""
    rows = db.execute(select(column, func.count()).group_by(column)).all()
    found = {value: count for value, count in rows}
    return [
        SeriesPointOut(label=title, value=found.get(code, 0)) for code, title in names.items()
    ]


def sources_status(db: Session) -> list[SourceStatusOut]:
    """Последний прогон по каждому источнику (FR-006)."""
    latest = (
        select(ParserRun.source_id, func.max(ParserRun.run_id).label("run_id"))
        .group_by(ParserRun.source_id)
        .subquery()
    )
    rows = db.execute(
        select(Source, ParserRun)
        .outerjoin(latest, latest.c.source_id == Source.source_id)
        .outerjoin(ParserRun, ParserRun.run_id == latest.c.run_id)
        .order_by(Source.source_id)
    ).all()

    return [
        SourceStatusOut(
            source_id=source.source_id,
            source_name=source.name,
            schedule=source.schedule,
            last_run_at=run.started_at if run else None,
            last_status=run.status if run else None,
            last_message=run.message if run else None,
            new_count=run.new_count if run else 0,
        )
        for source, run in rows
    ]


@router.get("", response_model=DashboardOut)
def dashboard(
    db: Session = Depends(get_db),
    admin: AppUser = Depends(require_role("admin")),
    days: int = Query(DEFAULT_PERIOD_DAYS, ge=7, le=180),
) -> DashboardOut:
    """Сводка для панели администратора: счётчики, графики, состояние источников."""
    return DashboardOut(
        counters=counters(db),
        registrations=registrations_by_day(db, days),
        applications_by_status=grouped(db, Application.status, APPLICATION_STATUS_NAMES),
        programs_by_status=grouped(db, Program.status, PROGRAM_STATUS_NAMES),
        users_by_role=grouped(
            db, AppUser.role, {k: v for k, v in ROLE_NAMES.items() if k != "guest"}
        ),
        sources=sources_status(db),
    )
