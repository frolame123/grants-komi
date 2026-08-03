"""Фоновые задачи по расписанию (FR-006, FR-011).

Расписание задано п. 4.2.6 ТЗ: ежесуточные источники опрашиваются каждый в
свой фиксированный час в интервале 02:00–05:00, еженедельные — по
понедельникам в том же интервале. Часы разнесены, одновременный запуск двух
адаптеров исключён.

Планировщик встроен в приложение и не требует отдельной инфраструктуры:
задания хранятся в памяти процесса и пересоздаются при запуске. Это
приемлемо, поскольку прогоны идемпотентны — повторный опрос источника не
создаёт дублей благодаря сопоставлению по паре «источник, ссылка».
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.aggregation import run_adapter
from app.db import SessionLocal
from app.models import Source
from app.notifications import build_daily_notifications

log = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

# Первый источник опрашивается в 02:00, каждый следующий часом позже
FIRST_HOUR = 2
LAST_HOUR = 5


async def poll_source(source_id: int) -> None:
    """Задание планировщика: опрос одного источника."""
    with SessionLocal() as db:
        source = db.get(Source, source_id)
        if source is None:
            log.warning("Источник %s удалён, задание пропущено", source_id)
            return
        run = await run_adapter(db, source)
        log.info(
            "Прогон источника «%s»: %s, новых %s, изменённых %s",
            source.name,
            run.status,
            run.new_count,
            run.updated_count,
        )


def trigger_for(index: int, schedule: str) -> CronTrigger:
    """Час запуска источника: разнесены по одному в час внутри интервала."""
    hour = FIRST_HOUR + index % (LAST_HOUR - FIRST_HOUR + 1)
    if schedule == "weekly":
        return CronTrigger(day_of_week="mon", hour=hour, minute=0)
    return CronTrigger(hour=hour, minute=0)


async def send_deadline_notifications() -> None:
    """Задание планировщика: ежедневное формирование уведомлений (FR-011)."""
    with SessionLocal() as db:
        counters = build_daily_notifications(db)
    log.info("Уведомления за сутки: %s", counters)


def setup_jobs() -> None:
    """Регистрация заданий по источникам из базы."""
    with SessionLocal() as db:
        sources = list(db.scalars(select(Source).order_by(Source.source_id)))

    for index, source in enumerate(sources):
        scheduler.add_job(
            poll_source,
            trigger=trigger_for(index, source.schedule),
            args=[source.source_id],
            id=f"poll_source_{source.source_id}",
            replace_existing=True,
            max_instances=1,  # долгий разбор не накладывается на следующий запуск
            coalesce=True,  # пропущенные запуски объединяются в один
        )
        log.info("Запланирован опрос источника «%s» (%s)", source.name, source.schedule)

    # Уведомления о сроках — ежедневно в 09:00 (п. 4.2.11 ТЗ)
    scheduler.add_job(
        send_deadline_notifications,
        trigger=CronTrigger(hour=9, minute=0),
        id="deadline_notifications",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    log.info("Запланировано формирование уведомлений о сроках, ежедневно в 09:00")


def start() -> None:
    if scheduler.running:
        return
    setup_jobs()
    scheduler.start()


def shutdown() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
