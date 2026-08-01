"""Ведение заявки по статусной модели (FR-008)."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.db import get_db
from app.models import AppUser, Application, ApplicationHistory, Program
from app.schemas import (
    ApplicationCreate,
    ApplicationOut,
    ApplicationTransition,
    HistoryOut,
    MessageOut,
)
from app.workflow import STATUS_NAMES, check_transition

router = APIRouter(prefix="/api/applications", tags=["Заявки"])


def to_out(application: Application) -> ApplicationOut:
    return ApplicationOut(
        application_id=application.application_id,
        program_id=application.program_id,
        program_title=application.program.title,
        status=application.status,
        status_name=STATUS_NAMES[application.status],
        status_date=application.status_date,
        result=application.result,
        comment=application.comment,
        program_archived=application.program.status == "ARCH",
        history=[
            HistoryOut(
                status=record.status,
                status_name=STATUS_NAMES[record.status],
                comment=record.comment,
                created_at=record.created_at,
            )
            for record in application.history
        ],
    )


def load(db: Session, application_id: int, user: AppUser) -> Application:
    """Заявка текущего пользователя. Чужие заявки недоступны."""
    application = db.scalar(
        select(Application)
        .options(selectinload(Application.history), selectinload(Application.program))
        .where(Application.application_id == application_id)
    )
    if application is None or application.user_id != user.user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Заявка не найдена")
    return application


@router.post("", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
def create_application(
    data: ApplicationCreate,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> ApplicationOut:
    """Создание черновика заявки по выбранной программе."""
    program = db.get(Program, data.program_id)
    if program is None or program.status != "PUB":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Программа не найдена")

    active = db.scalar(
        select(Application).where(
            Application.user_id == user.user_id,
            Application.program_id == data.program_id,
            Application.status != "RES",
        )
    )
    if active is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "По этой программе уже есть активная заявка"
        )

    application = Application(
        user_id=user.user_id,
        program_id=data.program_id,
        status="DRAFT",
        status_date=date.today(),
        comment=data.comment,
    )
    db.add(application)
    db.flush()
    db.add(
        ApplicationHistory(
            application_id=application.application_id,
            status="DRAFT",
            comment=data.comment,
            initiator_id=user.user_id,
        )
    )
    db.commit()
    return to_out(load(db, application.application_id, user))


@router.get("", response_model=list[ApplicationOut])
def list_applications(
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
    active_only: bool = Query(False, description="Только незавершённые заявки"),
) -> list[ApplicationOut]:
    statement = (
        select(Application)
        .options(selectinload(Application.history), selectinload(Application.program))
        .where(Application.user_id == user.user_id)
        .order_by(Application.status_date.desc())
    )
    if active_only:
        statement = statement.where(Application.status != "RES")
    return [to_out(application) for application in db.scalars(statement)]


@router.get("/{application_id}", response_model=ApplicationOut)
def get_application(
    application_id: int,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> ApplicationOut:
    return to_out(load(db, application_id, user))


@router.patch("/{application_id}", response_model=ApplicationOut)
def move_application(
    application_id: int,
    data: ApplicationTransition,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> ApplicationOut:
    """Перевод заявки в следующий статус с записью в историю переходов."""
    application = load(db, application_id, user)

    try:
        check_transition(
            application.status,
            data.status,
            program_archived=application.program.status == "ARCH",
            result=data.result,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    application.status = data.status
    application.result = data.result
    application.status_date = date.today()
    if data.comment is not None:
        application.comment = data.comment

    db.add(
        ApplicationHistory(
            application_id=application.application_id,
            status=data.status,
            comment=application.comment,
            initiator_id=user.user_id,
        )
    )
    db.commit()
    return to_out(load(db, application_id, user))


@router.delete("/{application_id}", response_model=MessageOut)
def delete_application(
    application_id: int,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> MessageOut:
    """Удаление заявки. Завершённая заявка не удаляется — она часть истории."""
    application = load(db, application_id, user)
    if application.status == "RES":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Завершённая заявка не удаляется"
        )
    db.delete(application)
    db.commit()
    return MessageOut(detail="Заявка удалена")
