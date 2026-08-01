"""Профиль организации-заявителя (FR-003)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models import AppUser, Category, OrgProfile
from app.schemas import CategoryOut, OrgProfileIn, OrgProfileOut

router = APIRouter(prefix="/api", tags=["Профиль организации"])


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)) -> list[Category]:
    """Справочник категорий: он же перечень отраслей для профиля (FR-016)."""
    return list(db.scalars(select(Category).order_by(Category.name)))


@router.get("/profile", response_model=OrgProfileOut)
def get_profile(
    db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)
) -> OrgProfile:
    profile = db.scalar(select(OrgProfile).where(OrgProfile.user_id == user.user_id))
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Профиль организации не заполнен")
    return profile


@router.put("/profile", response_model=OrgProfileOut)
def save_profile(
    data: OrgProfileIn,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
) -> OrgProfile:
    """Создание и редактирование профиля.

    Профиль один на пользователя: смена типа организации выполняется в нём же,
    новая запись не создаётся. ИНН уникален в системе — один ИНН, один профиль.
    """
    if db.get(Category, data.category_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Отрасль не найдена в справочнике")

    taken = db.scalar(
        select(OrgProfile).where(
            OrgProfile.inn == data.inn, OrgProfile.user_id != user.user_id
        )
    )
    if taken is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Организация с таким ИНН уже зарегистрирована. "
            "Если это ваша организация, восстановите доступ к существующей учётной записи",
        )

    profile = db.scalar(select(OrgProfile).where(OrgProfile.user_id == user.user_id))
    if profile is None:
        profile = OrgProfile(user_id=user.user_id)
        db.add(profile)

    for field, value in data.model_dump().items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)
    return profile
