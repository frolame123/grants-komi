"""Модерация и управление карточками программ (FR-007).

Очередь наполняется модулем агрегации (FR-006) и содержит записи двух типов:
NEW — программа, которой не было в базе, UPD — существенное изменение
существующей. Контент-менеджер публикует или отклоняет запись с указанием
причины, а опубликованные карточки правит напрямую, без очереди.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_role
from app.api.programs import to_out, with_relations
from app.audit import write_audit
from app.db import get_db
from app.dictionaries import APPROVED
from app.moderation import (
    changed_fields,
    check_publishable,
    check_reason,
    diff,
    restored_values,
    snapshot,
)
from app.models import (
    AppUser,
    Category,
    ModerationQueue,
    Program,
    ProgramApplicantType,
    ProgramRegion,
    Source,
)
from app.ratelimit import client_ip
from app.schemas import (
    ChangeOut,
    ModerationOut,
    ModerationPageOut,
    ProgramIn,
    ProgramOut,
    RejectIn,
)

router = APIRouter(prefix="/api/admin", tags=["Модерация"])

PAGE_SIZE = 20

QUEUE_STATUS_NAMES = {
    "waiting": "Ожидает рассмотрения",
    "approved": "Опубликовано",
    "rejected": "Отклонено",
}


def load_program(db: Session, program_id: int) -> Program:
    program = db.scalar(with_relations(select(Program).where(Program.program_id == program_id)))
    if program is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Программа не найдена")
    return program


def load_entry(db: Session, queue_id: int) -> ModerationQueue:
    entry = db.scalar(
        select(ModerationQueue)
        .options(selectinload(ModerationQueue.program))
        .where(ModerationQueue.queue_id == queue_id)
    )
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Запись очереди не найдена")
    return entry


def entry_out(db: Session, entry: ModerationQueue) -> ModerationOut:
    program = load_program(db, entry.program_id)
    changes = diff(entry.prev_snapshot, snapshot(program))
    return ModerationOut(
        queue_id=entry.queue_id,
        program_id=entry.program_id,
        program_title=program.title,
        program_status=program.status,
        change_type=entry.change_type,
        status=entry.status,
        status_name=QUEUE_STATUS_NAMES.get(entry.status, entry.status),
        reason=entry.reason,
        created_at=entry.created_at,
        resolved_at=entry.resolved_at,
        resolved_by=entry.resolved_by,
        changes=[ChangeOut(**change) for change in changes],
    )


def apply_fields(db: Session, program: Program, data: ProgramIn) -> None:
    """Перенос данных формы в карточку вместе с многозначными атрибутами."""
    if db.get(Source, data.source_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Источник не найден")
    if data.category_id is not None:
        category = db.get(Category, data.category_id)
        if category is None or category.status != APPROVED:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Категория не найдена в справочнике или ещё не утверждена",
            )

    program.source_id = data.source_id
    program.category_id = data.category_id
    program.title = data.title
    program.organizer = data.organizer
    program.amount = data.amount
    program.deadline = data.deadline
    program.source_url = data.source_url
    program.extra_json = data.extra_json

    program.applicant_types = [
        ProgramApplicantType(applicant_type=value) for value in sorted(set(data.applicant_types))
    ]
    program.regions = [
        ProgramRegion(region=value.strip())
        for value in sorted({r.strip() for r in data.regions if r.strip()})
    ]


@router.get("/moderation", response_model=ModerationPageOut)
def list_queue(
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_role("moderator", "admin")),
    queue_status: str | None = Query("waiting", alias="status"),
    change_type: str | None = None,
    page: int = Query(1, ge=1),
) -> ModerationPageOut:
    """Очередь модерации с представлением «было / стало» по каждой записи."""
    statement = select(ModerationQueue)
    if queue_status:
        statement = statement.where(ModerationQueue.status == queue_status)
    if change_type:
        statement = statement.where(ModerationQueue.change_type == change_type)

    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    statement = (
        statement.order_by(ModerationQueue.created_at.asc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    )

    return ModerationPageOut(
        items=[entry_out(db, entry) for entry in db.scalars(statement)],
        page=page,
        page_size=PAGE_SIZE,
        total=total,
    )


@router.get("/moderation/{queue_id}", response_model=ModerationOut)
def get_entry(
    queue_id: int,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_role("moderator", "admin")),
) -> ModerationOut:
    return entry_out(db, load_entry(db, queue_id))


@router.post("/moderation/{queue_id}/publish", response_model=ProgramOut)
def publish(
    queue_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_role("moderator", "admin")),
) -> ProgramOut:
    """Публикация карточки из очереди (FR-007)."""
    entry = load_entry(db, queue_id)
    if entry.status != "waiting":
        raise HTTPException(status.HTTP_409_CONFLICT, "Запись очереди уже рассмотрена")

    program = load_program(db, entry.program_id)
    try:
        check_publishable(program.category_id, program.deadline)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    program.status = "PUB"
    entry.status = "approved"
    entry.resolved_at = datetime.now()
    entry.resolved_by = user.user_id

    write_audit(
        db,
        action="program_publish",
        entity="program",
        entity_id=program.program_id,
        user_id=user.user_id,
        ip=client_ip(request),
    )
    db.commit()
    return to_out(load_program(db, program.program_id))


@router.post("/moderation/{queue_id}/reject", response_model=ModerationOut)
def reject(
    queue_id: int,
    data: RejectIn,
    request: Request,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_role("moderator", "admin")),
) -> ModerationOut:
    """Отклонение записи очереди с обязательной причиной (FR-007).

    Опубликованная карточка при отклонении изменения сохраняет прежнее
    содержимое — в базе оно уже обновлено парсером, поэтому изменённые поля
    восстанавливаются из снимка «было».
    """
    entry = load_entry(db, queue_id)
    if entry.status != "waiting":
        raise HTTPException(status.HTTP_409_CONFLICT, "Запись очереди уже рассмотрена")

    try:
        reason = check_reason(data.reason)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    program = load_program(db, entry.program_id)
    if entry.change_type == "NEW":
        # Новая карточка не публикуется и остаётся черновиком
        program.status = "DRAFT"
    elif entry.prev_snapshot:
        # Отклонение изменения: парсер уже записал новые данные, поэтому
        # прежнее содержимое возвращается из снимка (п. 4.2.7 ТЗ)
        values = restored_values(entry.prev_snapshot)
        types = values.pop("applicant_types")
        for field, value in values.items():
            setattr(program, field, value)
        program.applicant_types = [
            ProgramApplicantType(applicant_type=value) for value in types
        ]

    entry.status = "rejected"
    entry.reason = reason
    entry.resolved_at = datetime.now()
    entry.resolved_by = user.user_id

    write_audit(
        db,
        action="program_reject",
        entity="program",
        entity_id=program.program_id,
        user_id=user.user_id,
        ip=client_ip(request),
    )
    db.commit()
    return entry_out(db, entry)


@router.post("/programs", response_model=ProgramOut, status_code=status.HTTP_201_CREATED)
def create_program(
    data: ProgramIn,
    request: Request,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_role("moderator", "admin")),
) -> ProgramOut:
    """Создание карточки вручную.

    Нужно для программ из источников, которые не поддаются автоматическому
    разбору: п. 4.2.6 ТЗ прямо предусматривает наполнение таких источников
    через модерацию.
    """
    program = Program(status="DRAFT", content_hash="0" * 64)
    db.add(program)
    apply_fields(db, program, data)
    db.flush()

    write_audit(
        db,
        action="program_create",
        entity="program",
        entity_id=program.program_id,
        user_id=user.user_id,
        ip=client_ip(request),
    )
    db.commit()
    return to_out(load_program(db, program.program_id))


@router.put("/programs/{program_id}", response_model=ProgramOut)
def update_program(
    program_id: int,
    data: ProgramIn,
    request: Request,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_role("moderator", "admin")),
) -> ProgramOut:
    """Прямая правка карточки без очереди (FR-007).

    Каждое изменение фиксируется в журнале аудита с перечнем затронутых
    полей, поэтому перед правкой снимается снимок прежнего состояния.
    """
    program = load_program(db, program_id)
    before = snapshot(program)

    apply_fields(db, program, data)
    db.flush()
    after = snapshot(load_program(db, program_id))

    if program.status == "PUB":
        # Опубликованная карточка обязана сохранять категорию и срок
        try:
            check_publishable(program.category_id, program.deadline)
        except ValueError as exc:
            db.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    write_audit(
        db,
        action="program_update",
        entity="program",
        entity_id=program.program_id,
        user_id=user.user_id,
        ip=client_ip(request),
        details=f"изменены поля: {changed_fields(before, after)}",
    )
    db.commit()
    return to_out(load_program(db, program_id))


@router.post("/programs/{program_id}/archive", response_model=ProgramOut)
def archive_program(
    program_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_role("moderator", "admin")),
) -> ProgramOut:
    """Быстрое действие: снятие карточки с публикации."""
    program = load_program(db, program_id)
    if program.status == "ARCH":
        raise HTTPException(status.HTTP_409_CONFLICT, "Программа уже в архиве")

    program.status = "ARCH"
    write_audit(
        db,
        action="program_archive",
        entity="program",
        entity_id=program.program_id,
        user_id=user.user_id,
        ip=client_ip(request),
    )
    db.commit()
    return to_out(load_program(db, program_id))
