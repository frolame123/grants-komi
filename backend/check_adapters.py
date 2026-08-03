"""Самопроверка адаптеров источников (FR-006).

Разбор проверяется на сохранённой разметке, а не на живом сайте: проверка
должна давать один и тот же результат независимо от того, что сегодня
опубликовано на источнике и доступен ли он вообще.

Запуск:  python check_adapters.py
"""

import asyncio

from app.parsers.registry import ADAPTERS, SourceUnavailable, adapter_for
from app.parsers.rkomi import ORGANIZER, is_support_measure, parse_list

# Разметка повторяет структуру списка новостей econom.rkomi.ru: ссылка вида
# /presscenter/news/<номер>/ с заголовком внутри
SAMPLE_HTML = """
<div class="news">
  <a href="/presscenter/news/84509/">Продолжается прием заявок на конкурс «Успешный патент» 2026</a>
  <a href="/presscenter/news/84476/">Дайджест бизнес-новостей за 29 июля</a>
  <a href="/presscenter/news/84551/">В регионе определили победителей грантов Главы Республики</a>
  <a href="/presscenter/news/84600/">Объявлен приём заявок на гранты для НКО до 15.09.2026</a>
  <a href="/presscenter/news/84509/">Продолжается прием заявок на конкурс «Успешный патент» 2026</a>
  <a href="/presscenter/news/84470/">«Сыктывкарский Водоканал» стал участником проекта</a>
  <a href="/about/">О министерстве</a>
</div>
"""


def check_selection() -> None:
    """Из потока новостей отбираются только сообщения о мерах поддержки."""
    assert is_support_measure("Объявлен приём заявок на гранты для НКО")
    assert is_support_measure("Продолжается прием заявок на конкурс «Успешный патент»")
    assert is_support_measure("Стартовал приём заявок на субсидии")

    # Отчёты о результатах мерой поддержки не являются
    assert not is_support_measure("В регионе определили победителей грантов Главы Республики")
    assert not is_support_measure("Подвели итоги конкурса")
    assert not is_support_measure("Дайджест бизнес-новостей за 29 июля")
    assert not is_support_measure("Водоканал стал участником проекта")


def check_parsing() -> None:
    cards = parse_list(SAMPLE_HTML)
    titles = [card.title for card in cards]

    assert len(cards) == 2, f"ожидались две карточки, получено {len(cards)}: {titles}"
    assert all(card.organizer == ORGANIZER for card in cards)
    assert all(card.source_url.startswith("https://econom.rkomi.ru/presscenter/news/")
               for card in cards)
    assert all(card.complete for card in cards), "обязательные поля должны быть заполнены"

    # Повторяющаяся ссылка не создаёт вторую карточку
    assert len({card.source_url for card in cards}) == 2

    # Срок, если он назван в заголовке, извлекается; иначе остаётся пустым
    with_deadline = [card for card in cards if card.deadline]
    assert len(with_deadline) == 1, "срок из заголовка не распознан"
    assert with_deadline[0].deadline.isoformat() == "2026-09-15"
    assert "NKO" in with_deadline[0].applicant_types, "тип заявителя из заголовка"


def check_unavailable_sources() -> None:
    """Недоступные источники объясняют причину, а не молчат."""
    unavailable = 0
    for name in ADAPTERS:
        adapter = adapter_for(name)
        if type(adapter).__name__ != "UnavailableAdapter":
            continue
        unavailable += 1
        try:
            asyncio.run(adapter.fetch())
        except SourceUnavailable as exc:
            assert len(str(exc)) > 30, f"причина слишком краткая: {name}"
        else:
            raise AssertionError(f"источник {name} обязан сообщить о недоступности")

    assert unavailable == 3, "три источника из четырёх разбору не поддаются"


def check_unknown_source() -> None:
    """Источник без адаптера считается недоступным, а не ломает прогон."""
    adapter = adapter_for("Неизвестный источник")
    try:
        asyncio.run(adapter.fetch())
    except SourceUnavailable:
        return
    raise AssertionError("неизвестный источник должен сообщать о недоступности")


def main() -> None:
    for check in (check_selection, check_parsing, check_unavailable_sources, check_unknown_source):
        check()
        print(f"OK: {check.__name__}")


if __name__ == "__main__":
    main()
