"""Самопроверка правил формирования уведомлений (FR-011).

Проверяется выбор типа уведомления по числу дней до окончания приёма —
правило, от которого зависит, получит ли заявитель напоминание вовремя.

Запуск:  python check_notifications.py
"""

from app.notifications import (
    DEADLINE_LAST_DAY,
    DEADLINE_WARNING_DAYS,
    NEWP_LIMIT_PER_USER,
    NEWP_SCORE_THRESHOLD,
    TYPE_NAMES,
    deadline_type,
)


def check_deadline_types() -> None:
    """Пороги из п. 4.2.11 ТЗ: за 7 дней и за 1 день до окончания приёма."""
    assert deadline_type(7) == "DL7", "ровно неделя — первое напоминание"
    assert deadline_type(5) == "DL7"
    assert deadline_type(2) == "DL7"

    assert deadline_type(1) == "DL1", "последний день — повторное напоминание"
    assert deadline_type(0) == "DL1", "срок истекает сегодня"


def check_no_notification_outside_window() -> None:
    """Вне окна уведомления не создаются."""
    assert deadline_type(8) is None, "до срока больше недели"
    assert deadline_type(30) is None
    assert deadline_type(-1) is None, "срок уже прошёл"
    assert deadline_type(None) is None, "срок не определён"


def check_missed_run_recovery() -> None:
    """Границы нестрогие: пропущенный прогон не теряет уведомление.

    Если бы порог сравнивался на точное равенство, при пропуске суточного
    запуска пользователь остался бы без напоминания вовсе.
    """
    assert deadline_type(6) == "DL7", "прогон пропущен днём раньше — уведомление всё равно"
    assert deadline_type(4) == "DL7"
    assert deadline_type(0) == "DL1", "прогон пропущен накануне"


def check_constants() -> None:
    assert DEADLINE_WARNING_DAYS == 7 and DEADLINE_LAST_DAY == 1, "пороги заданы ТЗ"
    assert 0 < NEWP_SCORE_THRESHOLD <= 100, "порог соответствия в пределах шкалы"
    assert NEWP_LIMIT_PER_USER > 0, "ограничение на число сообщений за прогон"
    assert set(TYPE_NAMES) == {"DL7", "DL1", "NEWP"}, "классификатор типов из ТЗ"


def main() -> None:
    for check in (
        check_deadline_types,
        check_no_notification_outside_window,
        check_missed_run_recovery,
        check_constants,
    ):
        check()
        print(f"OK: {check.__name__}")


if __name__ == "__main__":
    main()
