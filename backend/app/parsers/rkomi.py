"""Адаптер источника «Минэкономразвития Республики Коми» (FR-006).

Что удалось выяснить о сайте econom.rkomi.ru при обследовании:

  * сертификат выдан удостоверяющим центром Минцифры — см. app/parsers/http.py;
  * страницы разделов и карточки новостей собираются в браузере скриптами,
    из разметки доступна только навигация;
  * список новостей отдаётся сервером и содержит заголовки со ссылками.

Поэтому адаптер работает по списку новостей: отбирает сообщения о приёме
заявок, конкурсах и грантах и создаёт по ним карточки. Сумма и срок подачи
из списка недоступны, они остаются незаполненными — и такая карточка по
п. 4.2.7 ТЗ не может быть опубликована автоматически, её дозаполняет
контент-менеджер. Это не обход требований, а предусмотренный ТЗ порядок для
источников, не поддающихся полному разбору (п. 4.2.6).
"""

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.parsers import RawProgram
from app.parsers.http import create_client, fetch
from app.parsers.normalize import (
    clean_text,
    parse_applicant_types,
    parse_date,
)

BASE_URL = "https://econom.rkomi.ru/"
LIST_URL = urljoin(BASE_URL, "presscenter/news/")
ORGANIZER = "Минэкономразвития Республики Коми"

NEWS_HREF = re.compile(r"/presscenter/news/\d+")

# Сообщения о мерах поддержки среди прочих новостей ведомства
KEYWORDS = (
    "грант",
    "субсид",
    "конкурс",
    "прием заявок",
    "приём заявок",
    "поддержк",
    "финансировани",
)

# Дайджесты и отчёты о результатах мерами поддержки не являются
EXCLUDED = ("дайджест", "итоги", "подвели", "победител", "вошел в топ", "вошёл в топ")

TITLE_LIMIT = 300


def is_support_measure(title: str) -> bool:
    """Отбор новостей, сообщающих о действующей мере поддержки."""
    lowered = title.lower()
    if any(word in lowered for word in EXCLUDED):
        return False
    return any(word in lowered for word in KEYWORDS)


def parse_list(html: str, base_url: str = BASE_URL) -> list[RawProgram]:
    """Разбор страницы списка новостей.

    Вынесен отдельно от загрузки, чтобы проверять на сохранённой разметке без
    обращения к сети.
    """
    soup = BeautifulSoup(html, "html.parser")
    cards: dict[str, RawProgram] = {}

    for link in soup.find_all("a", href=NEWS_HREF):
        title = clean_text(link.get_text(" ", strip=True), TITLE_LIMIT)
        if not title or not is_support_measure(title):
            continue

        url = urljoin(base_url, link["href"])
        if url in cards:
            continue

        cards[url] = RawProgram(
            title=title,
            organizer=ORGANIZER,
            source_url=url,
            deadline=parse_date(title),
            applicant_types=parse_applicant_types(title),
            regions=["Республика Коми"],
            extra={"источник": "раздел новостей", "требует_дозаполнения": True},
        )

    return list(cards.values())


class MinEconomAdapter:
    """Адаптер министерства экономического развития Республики Коми."""

    source_name = "Минэкономразвития Республики Коми"

    async def fetch(self) -> list[RawProgram]:
        async with create_client() as client:
            html = await fetch(client, LIST_URL)
        return parse_list(html)
