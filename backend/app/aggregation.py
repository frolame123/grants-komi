"""Ядро модуля агрегации: сопоставление карточек с базой (FR-006).

Что делает прогон источника:

1. адаптер возвращает список карточек;
2. результат проверяется целиком — если разбор явно сломался, прогон
   отбрасывается и данные в базе не меняются;
3. каждая карточка сопоставляется с базой по паре «источник, ссылка»;
4. новая попадает в базу черновиком и в очередь модерации с типом NEW;
5. существенно изменившаяся — в очередь с типом UPD;
6. изменившаяся косметически применяется сразу, без модерации;
7. неизменившаяся обновляет только дату последней проверки;
8. итог прогона записывается в лог.

Правила классификации общие с ручной модерацией и живут в app/moderation.py:
одно и то же изменение должно оцениваться одинаково независимо от того, кто
его внёс.
"""

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.moderation import is_significant, snapshot
from app.models import (
    ModerationQueue,
    ParserRun,
    Program,
    ProgramApplicantType,
    ProgramRegion,
    Source,
)
from app.parsers import RawProgram
from app.parsers.registry import adapter_for

log = logging.getLogger(__name__)

# Доля неразобранных карточек, выше которой результат прогона отбрасывается
BROKEN_SHARE_LIMIT = 0.5


@dataclass
class RunResult:
    """Счётчики прогона для записи в лог."""

    new_count: int = 0
    updated_count: int = 0
    cosmetic_count: int = 0
    unchanged_count: int = 0
    error_count: int = 0
    status: str = "success"
    message: str | None = None


def content_hash(raw: RawProgram) -> str:
    """Отпечаток содержимого карточки.

    Считается по значимым полям: по нему определяется, изменилось ли
    содержимое вообще. Поля разделены символом, который не встречается в
    данных, иначе «АБ» + «В» и «А» + «БВ» дали бы одинаковый отпечаток.
    """
    parts = [
        raw.title or "",
        raw.organizer or "",
        str(raw.amount or ""),
        raw.deadline.isoformat() if raw.deadline else "",
        ",".join(sorted(raw.applicant_types)),
        ",".join(sorted(raw.regions)),
        raw.source_url or "",
    ]
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def check_run_sanity(cards: list[RawProgram]) -> str | None:
    """Проверка правдоподобия результата прогона (FR-006).

    Возвращает причину отбраковки или None, если результат принимается.
    Разбор, вернувший ноль карточек или больше половины неразобранных, почти
    наверняка означает, что источник изменил вёрстку, а не что программы
    исчезли. Применять такой результат нельзя: он затёр бы каталог.
    """
    if not cards:
        return "разбор вернул ноль карточек, возможно изменение вёрстки источника"

    broken = sum(1 for card in cards if not card.complete)
    share = broken / len(cards)
    if share > BROKEN_SHARE_LIMIT:
        return (
            f"не разобрано {broken} карточек из {len(cards)} "
            f"({share:.0%}), возможно изменение вёрстки источника"
        )
    return None


def to_snapshot(raw: RawProgram, category_id: int | None) -> dict:
    """Снимок карточки источника в том же виде, что и снимок карточки базы."""
    return {
        "title": raw.title,
        "organizer": raw.organizer,
        "amount": str(raw.amount) if raw.amount is not None else None,
        "deadline": raw.deadline.isoformat() if raw.deadline else None,
        "applicant_types": sorted(raw.applicant_types),
        "category_id": category_id,
        "source_url": raw.source_url,
    }


def apply_to_program(program: Program, raw: RawProgram) -> None:
    """Перенос данных карточки источника в запись базы."""
    program.title = raw.title
    program.organizer = raw.organizer
    program.amount = raw.amount
    program.deadline = raw.deadline
    program.source_url = raw.source_url
    program.extra_json = raw.extra or {}
    program.content_hash = content_hash(raw)
    program.last_checked_at = datetime.now()
    program.applicant_types = [
        ProgramApplicantType(applicant_type=value) for value in sorted(set(raw.applicant_types))
    ]
    program.regions = [ProgramRegion(region=value) for value in sorted(set(raw.regions))]


def enqueue(db: Session, program: Program, change_type: str, prev: dict | None) -> None:
    """Постановка в очередь модерации со схлопыванием (FR-007).

    Если по программе уже есть нерассмотренная запись, создавать вторую
    нельзя: ограничение уникальности базы этого не допустит, да и ТЗ требует
    модерировать итоговое состояние, а не каждое промежуточное. Снимок
    «было» у существующей записи сохраняется — сравнивать нужно с тем
    состоянием, которое контент-менеджер видел последним.
    """
    existing = db.scalar(
        select(ModerationQueue).where(
            ModerationQueue.program_id == program.program_id,
            ModerationQueue.status == "waiting",
        )
    )
    if existing is not None:
        existing.change_type = change_type if existing.change_type == "NEW" else "UPD"
        return

    db.add(
        ModerationQueue(
            program_id=program.program_id,
            change_type=change_type,
            status="waiting",
            prev_snapshot=prev,
        )
    )


def process_card(db: Session, source_id: int, raw: RawProgram, result: RunResult) -> None:
    """Обработка одной карточки источника."""
    if not raw.complete:
        result.error_count += 1
        log.warning("Карточка не разобрана полностью: %s", raw.source_url or "без ссылки")
        return

    program = db.scalar(
        select(Program)
        .options(selectinload(Program.applicant_types), selectinload(Program.regions))
        .where(Program.source_id == source_id, Program.source_url == raw.source_url)
    )

    if program is None:
        program = Program(source_id=source_id, status="DRAFT")
        db.add(program)
        apply_to_program(program, raw)
        db.flush()
        enqueue(db, program, "NEW", None)
        result.new_count += 1
        return

    if program.content_hash == content_hash(raw):
        program.last_checked_at = datetime.now()
        result.unchanged_count += 1
        return

    before = snapshot(program)
    after = to_snapshot(raw, program.category_id)
    significant = is_significant(before, after)

    apply_to_program(program, raw)
    db.flush()

    if significant:
        enqueue(db, program, "UPD", before)
        result.updated_count += 1
    else:
        # Косметическое изменение применяется автоматически, с записью в лог
        log.info("Косметическое изменение карточки %s", program.program_id)
        result.cosmetic_count += 1


async def run_adapter(db: Session, source: Source) -> ParserRun:
    """Опрос источника адаптером и применение результата.

    Сбой адаптера — сетевой, разбора или полная недоступность источника — не
    прерывает работу остальных: исключение изолируется здесь и превращается в
    запись лога со статусом «источник недоступен». По п. 4.1.3 ТЗ деградация
    одного источника отказом системы не является.
    """
    started = datetime.now()
    try:
        cards = await adapter_for(source.name).fetch()
    except Exception as exc:  # noqa: BLE001 — причина уходит в лог целиком
        log.error("Источник «%s» недоступен: %s", source.name, exc)
        run = ParserRun(
            source_id=source.source_id,
            started_at=started,
            finished_at=datetime.now(),
            status="failed",
            message=str(exc)[:500],
        )
        db.add(run)
        db.commit()
        return run

    return run_source(db, source.source_id, cards)


def run_source(db: Session, source_id: int, cards: list[RawProgram]) -> ParserRun:
    """Применение результата прогона источника и запись в лог.

    Карточки применяются одной транзакцией: частично применённый прогон хуже,
    чем непримененный вовсе.
    """
    started = datetime.now()
    result = RunResult()

    reason = check_run_sanity(cards)
    if reason:
        result.status = "discarded"
        result.message = reason
        log.error("Прогон источника %s отброшен: %s", source_id, reason)
    else:
        for card in cards:
            process_card(db, source_id, card, result)

    run = ParserRun(
        source_id=source_id,
        started_at=started,
        finished_at=datetime.now(),
        status=result.status,
        new_count=result.new_count,
        updated_count=result.updated_count,
        archived_count=0,
        error_count=result.error_count,
        message=result.message,
    )
    db.add(run)
    db.commit()
    return run
