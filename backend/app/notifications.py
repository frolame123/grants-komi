"""Формирование уведомлений о сроках и новых программах (FR-011).

Ежедневно система обходит избранное и активные заявки пользователей и
создаёт уведомления трёх типов:

  DL7  — до окончания приёма осталась неделя;
  DL1  — приём заканчивается завтра;
  NEWP — появилась программа, подходящая профилю организации.

Повторная отправка уведомления того же типа по той же программе одному
пользователю исключена ограничением уникальности в базе, поэтому обход можно
запускать сколько угодно раз: лишних записей не появится.
"""

import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import mail
from app.matching import select_programs
from app.models import Application, AppUser, Favorite, Notification, OrgProfile, Program

log = logging.getLogger(__name__)

DEADLINE_WARNING_DAYS = 7
DEADLINE_LAST_DAY = 1

# Порог соответствия, начиная с которого программа считается подходящей для
# уведомления. Совпадения одной только отрасли (40 баллов) мало: сообщение
# должно быть поводом открыть карточку, а не шумом
NEWP_SCORE_THRESHOLD = 70

# Не более скольких сообщений о новых программах на пользователя за прогон.
# Ограничение защищает от лавины при первом запуске и после наполнения
# каталога крупной партией карточек
NEWP_LIMIT_PER_USER = 5

TYPE_NAMES = {
    "DL7": "До окончания приёма неделя",
    "DL1": "Приём заканчивается завтра",
    "NEWP": "Новая подходящая программа",
}


def deadline_type(days_left: int | None) -> str | None:
    """Тип уведомления по числу дней до окончания приёма.

    Границы нестрогие: если прогон был пропущен, уведомление всё равно
    отправится на следующий день, а не потеряется. Повтор исключён
    ограничением уникальности.
    """
    if days_left is None or days_left < 0:
        return None
    if days_left <= DEADLINE_LAST_DAY:
        return "DL1"
    if days_left <= DEADLINE_WARNING_DAYS:
        return "DL7"
    return None


def existing_keys(db: Session, user_id: int) -> set[tuple[int, str]]:
    """Уже отправленные пользователю уведомления: пара «программа, тип»."""
    rows = db.execute(
        select(Notification.program_id, Notification.type).where(
            Notification.user_id == user_id
        )
    ).all()
    return {(program_id, kind) for program_id, kind in rows}


def tracked_programs(db: Session, user_id: int) -> list[Program]:
    """Программы, за которыми следит пользователь: избранное и активные заявки."""
    favorites = select(Favorite.program_id).where(Favorite.user_id == user_id)
    applications = select(Application.program_id).where(
        Application.user_id == user_id, Application.status != "RES"
    )
    statement = select(Program).where(
        Program.program_id.in_(favorites.union(applications)),
        Program.status == "PUB",
    )
    return list(db.scalars(statement))


def matching_programs(db: Session, user: AppUser, today: date) -> list[tuple[Program, int]]:
    """Подходящие профилю программы с достаточной степенью соответствия."""
    profile = db.scalar(select(OrgProfile).where(OrgProfile.user_id == user.user_id))
    if profile is None or profile.category_id is None:
        return []

    programs = db.scalars(
        select(Program)
        .options(selectinload(Program.applicant_types), selectinload(Program.regions))
        .where(Program.status == "PUB")
    )
    return [
        (program, score)
        for program, score in select_programs(programs, profile, today)
        if score >= NEWP_SCORE_THRESHOLD
    ]


def notify(db: Session, user: AppUser, program: Program, kind: str) -> Notification:
    """Создание уведомления и, при согласии пользователя, письма."""
    notification = Notification(user_id=user.user_id, program_id=program.program_id, type=kind)
    db.add(notification)

    if user.email_notifications:
        mail.send_email(
            user.email,
            f"{TYPE_NAMES[kind]} — Гранты Коми",
            f"Программа: {program.title}\n"
            f"Организатор: {program.organizer}\n"
            f"Срок подачи: {program.deadline:%d.%m.%Y}\n\n"
            f"Подробности: {program.source_url}\n\n"
            "Отказаться от уведомлений по электронной почте можно в настройках.",
        )
    return notification


def build_daily_notifications(db: Session, today: date | None = None) -> dict[str, int]:
    """Ежедневный обход: уведомления о сроках и новых подходящих программах."""
    today = today or date.today()
    counters = {"DL7": 0, "DL1": 0, "NEWP": 0}

    users = list(db.scalars(select(AppUser).where(AppUser.status == "active")))
    for user in users:
        sent = existing_keys(db, user.user_id)

        for program in tracked_programs(db, user.user_id):
            days_left = (program.deadline - today).days if program.deadline else None
            kind = deadline_type(days_left)
            if kind and (program.program_id, kind) not in sent:
                notify(db, user, program, kind)
                sent.add((program.program_id, kind))
                counters[kind] += 1

        added = 0
        for program, _score in matching_programs(db, user, today):
            if added >= NEWP_LIMIT_PER_USER:
                break
            if (program.program_id, "NEWP") in sent:
                continue
            notify(db, user, program, "NEWP")
            sent.add((program.program_id, "NEWP"))
            counters["NEWP"] += 1
            added += 1

    db.commit()
    log.info(
        "Уведомления сформированы: за 7 дней %s, за 1 день %s, новых программ %s",
        counters["DL7"],
        counters["DL1"],
        counters["NEWP"],
    )
    return counters
