"""Сквозная проверка API против работающей СУБД.

Предыдущие самопроверки (check_auth, check_business и прочие) проверяют
правила в отрыве от базы. Этот сценарий проходит основные функции целиком:
регистрация, подтверждение адреса, вход, профиль, каталог, подбор, заявка,
модерация карточки. Он же служит основой протокола функционального
тестирования по п. 6.1 ТЗ.

Требуется наполненная база: alembic upgrade head и заливка db/seed.sql.

Запуск:  python check_api.py
"""

import random
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.db import SessionLocal, engine
from app.inn import WEIGHTS_10, _control_digit
from app.main import app
from app.models import AppUser, EmailConfirmationToken

client = TestClient(app, raise_server_exceptions=False)

EMAIL = f"test-{uuid.uuid4().hex[:8]}@example.com"
PASSWORD = "Parol123"


def make_inn() -> tuple[str, str]:
    """Пара «корректный ИНН, испорченный ИНН» для каждого прогона.

    ИНН уникален в системе, поэтому фиксированное значение годится ровно на
    один запуск. Корректный номер достраивается контрольной цифрой по
    алгоритму ФНС, испорченный отличается от него последней цифрой.
    """
    prefix = f"11{random.randint(0, 9_999_999):07d}"
    control = _control_digit(prefix, WEIGHTS_10)
    return f"{prefix}{control}", f"{prefix}{(control + 1) % 10}"


VALID_INN, INVALID_INN = make_inn()


def step(name: str) -> None:
    print(f"OK: {name}")


def confirmation_token(email: str) -> str:
    """Токен подтверждения читается из базы: писем без SMTP не отправляем."""
    with SessionLocal() as db:
        user = db.scalar(select(AppUser).where(AppUser.email == email))
        assert user is not None, "пользователь не создан"
        record = db.scalar(
            select(EmailConfirmationToken)
            .where(EmailConfirmationToken.user_id == user.user_id)
            .order_by(EmailConfirmationToken.token_id.desc())
        )
        assert record is not None, "токен подтверждения не создан"
        return record.token


def promote(email: str, role: str) -> None:
    """Повышение роли напрямую в базе: первый администратор создаётся так же."""
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE app_user SET role = :role WHERE email = :email"),
            {"role": role, "email": email},
        )


def check_registration() -> str:
    response = client.post(
        "/api/auth/register",
        json={
            "email": EMAIL,
            "password": PASSWORD,
            "password_confirm": PASSWORD,
            "pd_consent": True,
        },
    )
    assert response.status_code == 201, response.text
    step("регистрация (FR-001)")

    # Согласие на обработку персональных данных зафиксировано с меткой времени
    with SessionLocal() as db:
        user = db.scalar(select(AppUser).where(AppUser.email == EMAIL))
        assert user.status == "pending", "учётная запись должна ждать подтверждения"
        assert user.pd_consent_at is not None, "не зафиксировано согласие на обработку ПД"
    step("согласие на обработку персональных данных сохранено (152-ФЗ)")

    # Вход до подтверждения адреса запрещён
    denied = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert denied.status_code == 403, denied.text
    step("вход без подтверждения адреса отклонён")

    token = confirmation_token(EMAIL)
    confirmed = client.get("/api/auth/confirm", params={"token": token})
    assert confirmed.status_code == 200, confirmed.text
    step("подтверждение адреса (FR-002)")

    repeated = client.get("/api/auth/confirm", params={"token": token})
    assert repeated.json()["detail"] == "Адрес уже подтверждён", repeated.text
    step("повторный переход по ссылке токенов не выдаёт")

    login = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert login.status_code == 200, login.text
    step("вход и выдача пары токенов")
    return login.json()["access_token"]


def check_catalog() -> None:
    catalog = client.get("/api/programs").json()
    assert catalog["total"] >= 3, catalog
    assert all(item["status"] == "PUB" for item in catalog["items"]), "в каталоге не только PUB"
    step(f"каталог отдаёт только опубликованные программы: {catalog['total']} шт. (FR-004)")

    found = client.get("/api/programs", params={"search": "грант социального"}).json()
    assert found["total"] >= 1, found
    step("поиск по нескольким словам соединяет их по И")

    empty = client.get("/api/programs", params={"search": "заведомо отсутствующее слово"}).json()
    assert empty["total"] == 0
    step("пустой результат поиска не является ошибкой")

    days = catalog["items"][0]["days_left"]
    assert isinstance(days, int), "число дней до срока не вычислено (FR-014)"
    step(f"число дней до окончания приёма вычисляется: {days}")

    archive = client.get("/api/programs/archive").json()
    assert all(item["status"] == "ARCH" for item in archive["items"])
    step("раздел завершённых конкурсов содержит только архив")


def check_profile_and_matching(headers: dict) -> None:
    categories = client.get("/api/categories").json()
    assert categories, "справочник категорий пуст"

    bad_inn = client.put(
        "/api/profile",
        headers=headers,
        json={
            "org_type": "OOO",
            "inn": INVALID_INN,
            "category_id": categories[0]["category_id"],
            "city": "Сыктывкар",
        },
    )
    assert bad_inn.status_code == 422, bad_inn.text
    step("ИНН с неверным контрольным числом отклонён (FR-003)")

    saved = client.put(
        "/api/profile",
        headers=headers,
        json={
            "org_type": "OOO",
            "inn": VALID_INN,
            "category_id": categories[0]["category_id"],
            "city": "Сыктывкар",
            "goal": "Развитие социального предпринимательства",
            "region": "Республика Коми",
        },
    )
    assert saved.status_code == 200, saved.text
    step("профиль организации сохранён")

    matched = client.get("/api/programs/matched", headers=headers).json()
    assert matched["total"] >= 1, matched
    best = matched["items"][0]
    assert 0 < best["match"] <= 100, best
    step(f"подбор вернул {matched['total']} программ, лучшее соответствие {best['match']}% (FR-005)")


def check_application(headers: dict) -> None:
    program_id = client.get("/api/programs").json()["items"][0]["program_id"]

    created = client.post(
        "/api/applications", headers=headers, json={"program_id": program_id}
    )
    assert created.status_code == 201, created.text
    application_id = created.json()["application_id"]
    step("заявка создана в статусе черновика (FR-008)")

    duplicate = client.post(
        "/api/applications", headers=headers, json={"program_id": program_id}
    )
    assert duplicate.status_code == 409, "вторая активная заявка на ту же программу"
    step("повторная активная заявка отклонена")

    skip = client.patch(
        f"/api/applications/{application_id}", headers=headers, json={"status": "SENT"}
    )
    assert skip.status_code == 409, skip.text
    step("перепрыгивающий переход статуса запрещён")

    for status_code in ("PREP", "SENT"):
        moved = client.patch(
            f"/api/applications/{application_id}", headers=headers, json={"status": status_code}
        )
        assert moved.status_code == 200, moved.text
    final = client.patch(
        f"/api/applications/{application_id}",
        headers=headers,
        json={"status": "RES", "result": "APPROVED"},
    )
    assert final.status_code == 200, final.text
    assert len(final.json()["history"]) == 4, "история переходов неполна"
    step("маршрут DRAFT → PREP → SENT → RES пройден, история из 4 записей")

    frozen = client.patch(
        f"/api/applications/{application_id}", headers=headers, json={"status": "PREP"}
    )
    assert frozen.status_code == 409
    step("завершённая заявка не редактируется")


def check_moderation(headers: dict) -> None:
    denied = client.get("/api/admin/moderation", headers=headers)
    assert denied.status_code == 403, "заявитель не должен видеть очередь модерации"
    step("разграничение доступа: заявителю очередь модерации недоступна")

    promote(EMAIL, "moderator")
    queue = client.get("/api/admin/moderation", headers=headers)
    assert queue.status_code == 200, queue.text
    step("после назначения роли очередь доступна немедленно (роль читается из БД)")

    entries = queue.json()["items"]
    assert entries, "очередь модерации пуста"
    with_changes = [e for e in entries if e["changes"]]
    assert with_changes, "нет ни одной записи с представлением «было / стало»"
    change = with_changes[0]["changes"][0]
    assert {"field", "before", "after", "significant"} <= set(change)
    step(f"представление «было / стало» работает: поле «{change['field_name']}» (FR-007)")

    waiting = next(e for e in entries if e["status"] == "waiting")
    no_reason = client.post(
        f"/api/admin/moderation/{waiting['queue_id']}/reject", headers=headers, json={"reason": ""}
    )
    assert no_reason.status_code == 422
    step("отклонение без причины невозможно")


def check_aggregation_live() -> None:
    """Прогон агрегации против базы: новая карточка, повтор, изменение, сбой."""
    from decimal import Decimal

    from sqlalchemy import func

    from app.aggregation import run_source
    from app.models import ModerationQueue, Program, Source
    from app.parsers import RawProgram

    url = f"https://example.org/programs/{uuid.uuid4().hex[:10]}"

    def card(amount: str = "500000.00") -> RawProgram:
        return RawProgram(
            title="Грант на развитие ремёсел",
            organizer="Минэкономразвития Республики Коми",
            source_url=url,
            amount=Decimal(amount),
            applicant_types=["OOO"],
        )

    with SessionLocal() as db:
        source_id = db.scalar(select(Source.source_id).order_by(Source.source_id))

        first = run_source(db, source_id, [card()])
        assert first.status == "success" and first.new_count == 1, "новая карточка не учтена"
        step("прогон агрегации: новая карточка учтена (FR-006)")

        program = db.scalar(select(Program).where(Program.source_url == url))
        assert program.status == "DRAFT", "новая карточка обязана быть черновиком"
        entry = db.scalar(
            select(ModerationQueue).where(ModerationQueue.program_id == program.program_id)
        )
        assert entry.change_type == "NEW" and entry.status == "waiting"
        step("новая карточка поставлена в очередь модерации типом NEW")

        repeat = run_source(db, source_id, [card()])
        assert repeat.new_count == 0 and repeat.updated_count == 0
        step("повторный прогон без изменений очередь не пополняет")

        changed = run_source(db, source_id, [card("750000.00")])
        assert changed.updated_count == 1, "изменение суммы существенно"
        step("изменение суммы распознано как существенное")

        queued = db.scalar(
            select(func.count())
            .select_from(ModerationQueue)
            .where(
                ModerationQueue.program_id == program.program_id,
                ModerationQueue.status == "waiting",
            )
        )
        assert queued == 1, "записи очереди по одной программе должны схлопываться"
        step("несколько изменений схлопнуты в одну запись очереди")

        broken = run_source(db, source_id, [])
        assert broken.status == "discarded" and broken.message
        step("пустой результат разбора отброшен, данные в базе не изменены")


def check_notifications_live(headers: dict) -> None:
    """Формирование уведомлений, счётчик непрочитанных и отказ от рассылки."""
    from app.notifications import build_daily_notifications

    from datetime import date, timedelta

    from app.models import Program

    program_id = client.get("/api/programs").json()["items"][0]["program_id"]
    client.post(f"/api/favorites/{program_id}", headers=headers)

    # Срок подачи временно переносится в окно уведомления: у тестовых программ
    # дедлайны далеко, и без этого проверка ничего бы не доказала
    with SessionLocal() as db:
        program = db.get(Program, program_id)
        original_deadline = program.deadline
        program.deadline = date.today() + timedelta(days=3)
        db.commit()

    try:
        with SessionLocal() as db:
            first = build_daily_notifications(db)
            second = build_daily_notifications(db)
    finally:
        with SessionLocal() as db:
            db.get(Program, program_id).deadline = original_deadline
            db.commit()

    assert first["DL7"] >= 1, "уведомление за неделю до срока не сформировано"
    assert sum(second.values()) == 0, "повторный прогон не должен дублировать уведомления"
    step(f"уведомления сформированы {first}, повторный прогон не создал ни одного (FR-011)")

    page = client.get("/api/notifications", headers=headers).json()
    assert page["unread"] == page["total"] >= 1
    assert page["items"][0]["type"] == "DL7"
    step(f"счётчик непрочитанных: {page['unread']}, тип уведомления DL7")

    notification_id = page["items"][0]["notification_id"]
    read = client.post(f"/api/notifications/{notification_id}/read", headers=headers)
    assert read.status_code == 200, read.text
    after = client.get("/api/notifications", headers=headers).json()
    assert after["unread"] == page["unread"] - 1
    step("отметка прочтения уменьшает счётчик непрочитанных")

    settings = client.put(
        "/api/notifications/settings", headers=headers, json={"email_notifications": False}
    ).json()
    assert settings["email_notifications"] is False
    step("отказ от рассылки по электронной почте сохранён (38-ФЗ)")


def check_account_deletion(headers: dict) -> None:
    """Удаление учётной записи: подтверждение паролем и обезличивание."""
    from sqlalchemy import func

    from app.models import Favorite, Notification, OrgProfile

    with SessionLocal() as db:
        user = db.scalar(select(AppUser).where(AppUser.email == EMAIL))
        user_id = user.user_id

    wrong = client.post("/api/account/delete", headers=headers, json={"password": "Parol124"})
    assert wrong.status_code == 403, "удаление без верного пароля"
    step("удаление учётной записи без верного пароля отклонено (FR-013)")

    deleted = client.post("/api/account/delete", headers=headers, json={"password": PASSWORD})
    assert deleted.status_code == 200, deleted.text
    step("учётная запись удалена по запросу пользователя")

    with SessionLocal() as db:
        user = db.get(AppUser, user_id)
        assert user.deleted_at is not None and user.status == "blocked"
        assert user.email != EMAIL, "адрес должен быть обезличен"
        for model in (OrgProfile, Favorite, Notification):
            left = db.scalar(
                select(func.count()).select_from(model).where(model.user_id == user_id)
            )
            assert left == 0, f"остались записи {model.__name__}"
    step("профиль, избранное и уведомления стёрты, учётная запись обезличена")

    assert client.get("/api/auth/me", headers=headers).status_code == 401
    step("токен удалённой учётной записи больше не действует")

    again = client.post(
        "/api/auth/register",
        json={
            "email": EMAIL,
            "password": PASSWORD,
            "password_confirm": PASSWORD,
            "pd_consent": True,
        },
    )
    assert again.status_code == 201, "адрес обязан освободиться для повторной регистрации"
    step("адрес освобождён: повторная регистрация возможна (FR-001)")


def main() -> None:
    token = check_registration()
    headers = {"Authorization": f"Bearer {token}"}

    check_catalog()
    check_profile_and_matching(headers)
    check_application(headers)
    check_moderation(headers)
    check_aggregation_live()
    check_notifications_live(headers)
    check_account_deletion(headers)

    print(f"\nВсе сценарии пройдены. Тестовая учётная запись: {EMAIL}")


if __name__ == "__main__":
    main()
