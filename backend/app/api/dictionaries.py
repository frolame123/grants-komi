"""Ведение справочников (FR-016).

Регламент из п. 4.2.16 ТЗ: значение предлагает контент-менеджер, утверждает
администратор, удаление не допускается — дубли объединяются с переносом всех
ссылок. Все операции фиксируются в журнале аудита.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.audit import write_audit
from app.db import get_db
from app.dictionaries import (
    APPROVED,
    MERGED,
    PROPOSED,
    STATUS_NAMES,
    check_approve,
    check_merge,
    check_unique,
    normalize_name,
)
from app.models import AppUser, Category, OrgProfile, Program
from app.ratelimit import client_ip
from app.schemas import CategoryAdminOut, CategoryIn, CategoryMergeIn, MessageOut

router = APIRouter(prefix="/api/admin/dictionaries/categories", tags=["Справочники"])


def usage(db: Session, category_id: int) -> tuple[int, int]:
    """Сколько программ и профилей ссылается на значение."""
    programs = db.scalar(
        select(func.count()).select_from(Program).where(Program.category_id == category_id)
    )
    profiles = db.scalar(
        select(func.count()).select_from(OrgProfile).where(OrgProfile.category_id == category_id)
    )
    return programs or 0, profiles or 0


def to_out(db: Session, category: Category) -> CategoryAdminOut:
    programs, profiles = usage(db, category.category_id)
    return CategoryAdminOut(
        category_id=category.category_id,
        name=category.name,
        status=category.status,
        status_name=STATUS_NAMES.get(category.status, category.status),
        proposed_by=category.proposed_by,
        merged_into_id=category.merged_into_id,
        created_at=category.created_at,
        usage_programs=programs,
        usage_profiles=profiles,
    )


def load(db: Session, category_id: int) -> Category:
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Значение справочника не найдено")
    return category


@router.get("", response_model=list[CategoryAdminOut])
def list_categories(
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_role("moderator", "admin")),
    category_status: str | None = Query(None, alias="status"),
) -> list[CategoryAdminOut]:
    """Полный справочник, включая предложенные и объединённые значения."""
    statement = select(Category).order_by(Category.name)
    if category_status:
        statement = statement.where(Category.status == category_status)
    return [to_out(db, category) for category in db.scalars(statement)]


@router.post("", response_model=CategoryAdminOut, status_code=status.HTTP_201_CREATED)
def propose_category(
    data: CategoryIn,
    request: Request,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_role("moderator", "admin")),
) -> CategoryAdminOut:
    """Предложение нового значения справочника.

    Контент-менеджер предлагает, значение появляется в состоянии «предложено»
    и в каталоге пока не участвует. Администратор, предлагая значение,
    утверждает его сразу — отдельного согласования ему не у кого просить.
    """
    try:
        name = normalize_name(data.name)
        check_unique(name, set(db.scalars(select(Category.name))))
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    category = Category(
        name=name,
        status=APPROVED if user.role == "admin" else PROPOSED,
        proposed_by=user.user_id,
    )
    db.add(category)
    db.flush()

    write_audit(
        db,
        action="dict_propose",
        entity="category",
        entity_id=category.category_id,
        user_id=user.user_id,
        ip=client_ip(request),
    )
    db.commit()
    db.refresh(category)
    return to_out(db, category)


@router.post("/{category_id}/approve", response_model=CategoryAdminOut)
def approve_category(
    category_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: AppUser = Depends(require_role("admin")),
) -> CategoryAdminOut:
    """Утверждение предложенного значения администратором."""
    category = load(db, category_id)
    try:
        check_approve(category.status)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    category.status = APPROVED
    write_audit(
        db,
        action="dict_approve",
        entity="category",
        entity_id=category.category_id,
        user_id=admin.user_id,
        ip=client_ip(request),
    )
    db.commit()
    return to_out(db, category)


@router.post("/{category_id}/merge", response_model=CategoryAdminOut)
def merge_category(
    category_id: int,
    data: CategoryMergeIn,
    request: Request,
    db: Session = Depends(get_db),
    admin: AppUser = Depends(require_role("admin")),
) -> CategoryAdminOut:
    """Объединение дубля с существующим значением (FR-016).

    Удаление значений справочника не допускается: программы и профили,
    ссылающиеся на дубль, потеряли бы категорию. Вместо удаления все ссылки
    переносятся на утверждённое значение, а строка дубля сохраняется с
    отметкой, во что она объединена.
    """
    source = load(db, category_id)
    target = load(db, data.target_id)

    try:
        check_merge(source.category_id, source.status, target.category_id, target.status)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    # Перенос ссылок выполняется одним запросом на таблицу, а не по одной
    # записи: операция должна быть атомарной в пределах транзакции
    db.execute(
        update(Program)
        .where(Program.category_id == source.category_id)
        .values(category_id=target.category_id)
    )
    db.execute(
        update(OrgProfile)
        .where(OrgProfile.category_id == source.category_id)
        .values(category_id=target.category_id)
    )

    source.status = MERGED
    source.merged_into_id = target.category_id

    write_audit(
        db,
        action="dict_merge",
        entity="category",
        entity_id=source.category_id,
        user_id=admin.user_id,
        ip=client_ip(request),
        details=f"объединено со значением {target.category_id} «{target.name}»",
    )
    db.commit()
    return to_out(db, source)


@router.delete("/{category_id}", response_model=MessageOut)
def delete_category(
    category_id: int,
    admin: AppUser = Depends(require_role("admin")),
) -> MessageOut:
    """Удаление значений справочника не предусмотрено (п. 4.2.16 ТЗ).

    Маршрут существует только для того, чтобы дать внятный ответ вместо
    ошибки 405: удаление — типовое ожидание, и объяснить его отсутствие
    лучше сразу.
    """
    raise HTTPException(
        status.HTTP_405_METHOD_NOT_ALLOWED,
        "Значения справочника не удаляются. Объедините дубль с существующим "
        "значением: POST /api/admin/dictionaries/categories/{id}/merge",
    )
