"""Адаптер источника «Портал госфинподдержки» (promote.budget.gov.ru).

Единый портал бюджетной системы Минфина России публикует отборы и субсидии
всех уровней бюджета. Данные отдаёт JSON-API (POST list-activity-card), поиск
по ключевым словам сужает выборку. Из всероссийского перечня отбираем отборы,
организатор которых — орган власти Республики Коми (поле pppItemName).

Сумма и срок берутся из карточки; тип заявителя в списке закодирован иначе,
чем в системе, поэтому оставляется пустым — такую карточку по п. 4.2.7 ТЗ
дозаполняет контент-менеджер (тот же порядок, что у остальных источников).
"""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import httpx

from app.parsers import RawProgram

API_URL = "https://promote.budget.gov.ru/m-data/api/v1/activity/public-view/list-activity-card"
CARD_URL = "https://promote.budget.gov.ru/public/minfin/activity/selection/{cid}"

PAGES = 8          # сколько страниц перебрать
PER_PAGE = 20
KEYWORD = "Коми"   # сужает всероссийский перечень до региона

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "GrantyKomi/1.0 (aggregation bot)",
}

TITLE_LIMIT = 300
ORG_LIMIT = 200


def request_body(page: int) -> dict:
    """Тело запроса списка: пустые фильтры, поиск по ключевому слову региона."""
    return {
        "currentPage": page, "entryCount": PER_PAGE,
        "recipientCategory": [], "recipientSelectionWayId": [],
        "minActivityAmountForPerson": None, "maxActivityAmountForPerson": None,
        "coFinancing": [], "activityYear": [], "subsidyTypeId": [], "budgetType": [],
        "activityCategory": [], "directionId": [], "okvedId": [],
        "textTerms": [KEYWORD], "realizationPlace": [], "pppCode": [],
        "activityType": [], "maxAmountType": [], "distributionType": [],
        "sortDirection": 0, "sortMember": "Default", "isSelection": True,
        "geography": [], "tags": [], "selectionLicenseRequired": [],
        "accreditationRequired": [], "selectionType": 0, "soOktmos": [],
    }


def parse_amount(text: str | None) -> Decimal | None:
    """Сумма из строки вида «354 970 000,00 ₽». Нечисловые («не установлен») → None."""
    if not text:
        return None
    match = re.search(r"\d[\d  ]*(?:,\d+)?", text)
    if not match:
        return None
    raw = match.group(0).replace(" ", "").replace(" ", "").replace(",", ".")
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return None
    return value if value > 0 else None


def parse_deadline(iso: str | None):
    """Срок подачи из ISO-даты вида «2026-06-01T20:59:00Z»."""
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def is_komi(card: dict) -> bool:
    """Отбор: организатор — орган власти Республики Коми."""
    return "коми" in (card.get("pppItemName") or "").lower()


def is_open(card: dict, today: date | None = None) -> bool:
    """Приём заявок ещё идёт: статус не «Завершен» и срок не в прошлом.

    Статусной строке доверять нельзя (встречаются карточки с прошедшим сроком
    и статусом не «Завершен»), поэтому решает дата: карточку без срока пропускаем
    (её досмотрит модерация), карточку с прошедшим сроком — отбрасываем.
    """
    info = card.get("selectionAcceptingApplicationInfo") or {}
    if "заверш" in (info.get("acceptingApplicationsInfo") or "").lower():
        return False
    deadline = parse_deadline(card.get("endDate"))
    if deadline is None:
        return True
    return deadline >= (today or date.today())


def cards_to_programs(items: list[dict], today: date | None = None) -> list[RawProgram]:
    """Разбор списка карточек. Вынесен отдельно — проверяется без сети."""
    programs: list[RawProgram] = []
    for card in items:
        if not is_komi(card) or not is_open(card, today):
            continue
        cid = card.get("competitionId") or card.get("activityId")
        title = (card.get("title") or "").strip()[:TITLE_LIMIT]
        organizer = (card.get("pppItemName") or "").strip()[:ORG_LIMIT]
        programs.append(
            RawProgram(
                title=title or None,
                organizer=organizer or None,
                source_url=CARD_URL.format(cid=cid) if cid else None,
                amount=parse_amount(card.get("maxAmountForPersonInfo")),
                deadline=parse_deadline(card.get("endDate")),
                regions=["Республика Коми"],
                extra={
                    "источник": "promote.budget.gov.ru",
                    "требует_дозаполнения": True,
                },
            )
        )
    return programs


class PromoteAdapter:
    """Адаптер портала государственной финансовой поддержки (Минфин России)."""

    source_name = "Портал госфинподдержки (Минфин России)"

    async def fetch(self) -> list[RawProgram]:
        collected: list[RawProgram] = []
        async with httpx.AsyncClient(timeout=20, headers=HEADERS) as client:
            for page in range(1, PAGES + 1):
                response = await client.post(API_URL, json=request_body(page))
                response.raise_for_status()
                items = response.json()["item1"]["items"]
                if not items:
                    break
                collected.extend(cards_to_programs(items))
        return collected
