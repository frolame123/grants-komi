"""Каталог программ, персональный подбор и избранное (FR-004, FR-005, FR-014)."""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.db import get_db
from app.matching import select_programs
from app.models import AppUser, Favorite, OrgProfile, Program
from app.schemas import MessageOut, PageOut, ProgramOut

router = APIRouter(prefix="/api", tags=["Каталог программ"])

PAGE_SIZE = 20  # п. 4.2.4 ТЗ: 20 записей на страницу


def to_out(program: Program, match: int | None = None) -> ProgramOut:
    return ProgramOut(
        program_id=program.program_id,
        title=program.title,
        organizer=program.organizer,
        amount=program.amount,
        deadline=program.deadline,
        days_left=program.days_left,
        status=program.status,
        category_id=program.category_id,
        category=program.category.name if program.category else None,
        source=program.source.name,
        source_url=program.source_url,
        applicant_types=sorted(t.applicant_type for t in program.applicant_types),
        regions=sorted(r.region for r in program.regions),
        extra_json=program.extra_json,
        match=match,
    )


def with_relations(statement: Select) -> Select:
    return statement.options(
        selectinload(Program.applicant_types),
        selectinload(Program.regions),
        selectinload(Program.category),
        selectinload(Program.source),
    )


def apply_search(statement: Select, search: str | None) -> Select:
    """Поиск по нескольким словам: слова соединяются по И, регистр не учитывается."""
    for word in (search or "").split():
        pattern = f"%{word}%"
        statement = statement.where(
            or_(Program.title.ilike(pattern), Program.organizer.ilike(pattern))
        )
    return statement


@router.get("/programs", response_model=PageOut)
def list_programs(
    db: Session = Depends(get_db),
    search: str | None = Query(None, max_length=100),
    category_id: int | None = None,
    applicant_type: Literal["IP", "OOO", "NKO", "SMZ"] | None = None,
    amount_min: int | None = Query(None, ge=0),
    amount_max: int | None = Query(None, ge=0),
    deadline_before: date | None = None,
    sort: Literal["deadline", "amount"] = "deadline",
    order: Literal["asc", "desc"] = "asc",
    page: int = Query(1, ge=1),
) -> PageOut:
    """Каталог: только опубликованные программы, поиск, фильтры, сортировка (FR-004)."""
    statement = select(Program).where(Program.status == "PUB")
    statement = apply_search(statement, search)

    if category_id is not None:
        statement = statement.where(Program.category_id == category_id)
    if applicant_type is not None:
        statement = statement.where(
            Program.applicant_types.any(applicant_type=applicant_type)
        )
    if amount_min is not None:
        statement = statement.where(Program.amount >= amount_min)
    if amount_max is not None:
        statement = statement.where(Program.amount <= amount_max)
    if deadline_before is not None:
        statement = statement.where(Program.deadline <= deadline_before)

    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0

    column = Program.deadline if sort == "deadline" else Program.amount
    statement = statement.order_by(column.asc() if order == "asc" else column.desc())
    statement = with_relations(statement).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)

    return PageOut(
        items=[to_out(p) for p in db.scalars(statement)],
        page=page,
        page_size=PAGE_SIZE,
        total=total,
    )


@router.get("/programs/archive", response_model=PageOut)
def list_archive(
    db: Session = Depends(get_db),
    search: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
) -> PageOut:
    """Раздел «Завершённые конкурсы»: только программы в архиве (FR-004)."""
    statement = apply_search(select(Program).where(Program.status == "ARCH"), search)
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    statement = with_relations(statement).order_by(Program.deadline.desc())
    statement = statement.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)

    return PageOut(
        items=[to_out(p) for p in db.scalars(statement)],
        page=page,
        page_size=PAGE_SIZE,
        total=total,
    )


@router.get("/programs/matched", response_model=PageOut)
def matched_programs(
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
    page: int = Query(1, ge=1),
) -> PageOut:
    """Персональный подбор под профиль организации (FR-005).

    Результат не кэшируется: правка профиля и каталога учитывается сразу.
    """
    profile = db.scalar(select(OrgProfile).where(OrgProfile.user_id == user.user_id))
    if profile is None or profile.category_id is None:
        raise HTTPException(
            status.HTTP_412_PRECONDITION_FAILED,
            "Для подбора заполните тип организации и отрасль в профиле",
        )

    programs = db.scalars(with_relations(select(Program).where(Program.status == "PUB")))
    matched = select_programs(programs, profile, date.today())
    page_items = matched[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]

    return PageOut(
        items=[to_out(program, score) for program, score in page_items],
        page=page,
        page_size=PAGE_SIZE,
        total=len(matched),
    )


@router.get("/programs/{program_id}", response_model=ProgramOut)
def get_program(program_id: int, db: Session = Depends(get_db)) -> ProgramOut:
    """Карточка программы. Черновики и записи на модерации наружу не отдаются."""
    program = db.scalar(with_relations(select(Program).where(Program.program_id == program_id)))
    if program is None or program.status not in ("PUB", "ARCH"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Программа не найдена")
    return to_out(program)


@router.get("/favorites", response_model=PageOut)
def list_favorites(
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
    page: int = Query(1, ge=1),
) -> PageOut:
    statement = (
        select(Program)
        .join(Favorite, Favorite.program_id == Program.program_id)
        .where(Favorite.user_id == user.user_id)
    )
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    statement = with_relations(statement).order_by(Program.deadline.asc())
    statement = statement.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)

    return PageOut(
        items=[to_out(p) for p in db.scalars(statement)],
        page=page,
        page_size=PAGE_SIZE,
        total=total,
    )


@router.post("/favorites/{program_id}", response_model=MessageOut)
def add_favorite(
    program_id: int,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> MessageOut:
    if db.get(Program, program_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Программа не найдена")

    existing = db.scalar(
        select(Favorite).where(
            Favorite.user_id == user.user_id, Favorite.program_id == program_id
        )
    )
    if existing is None:
        db.add(Favorite(user_id=user.user_id, program_id=program_id))
        db.commit()
    return MessageOut(detail="Программа добавлена в избранное")


@router.delete("/favorites/{program_id}", response_model=MessageOut)
def remove_favorite(
    program_id: int,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> MessageOut:
    favorite = db.scalar(
        select(Favorite).where(
            Favorite.user_id == user.user_id, Favorite.program_id == program_id
        )
    )
    if favorite is not None:
        db.delete(favorite)
        db.commit()
    return MessageOut(detail="Программа удалена из избранного")
