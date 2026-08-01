"""Ограничение частоты запросов (п. 4.1.4 ТЗ).

Лимиты: вход — 5 неудачных попыток с одного IP за 15 минут с последующей
блокировкой на 15 минут; регистрация — 5 с одного IP в час; API — 100
запросов в минуту с одного IP.

ponytail: счётчики в памяти процесса. Приложение разворачивается одним
контейнером на одном VPS (п. 4.3.4 ТЗ), общего хранилища для лимитов не
требуется. При переходе на несколько воркеров — вынести в Redis.
"""

import time
from collections import defaultdict, deque

WINDOW_LOGIN = 15 * 60
WINDOW_REGISTER = 60 * 60
WINDOW_API = 60

LIMIT_LOGIN = 5
LIMIT_REGISTER = 5
LIMIT_API = 100


class SlidingWindow:
    """Счётчик событий по ключу в скользящем окне."""

    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def _trim(self, key: str, now: float) -> deque[float]:
        events = self._events[key]
        while events and now - events[0] > self.window:
            events.popleft()
        return events

    def hit(self, key: str) -> bool:
        """Учесть событие. False — лимит исчерпан (событие всё равно учтено)."""
        now = time.monotonic()
        events = self._trim(key, now)
        events.append(now)
        return len(events) <= self.limit

    def exceeded(self, key: str) -> bool:
        """Лимит исчерпан без учёта нового события."""
        return len(self._trim(key, time.monotonic())) > self.limit

    def reset(self, key: str) -> None:
        self._events.pop(key, None)

    def retry_after(self, key: str) -> int:
        """Через сколько секунд освободится место в окне."""
        events = self._events.get(key)
        if not events:
            return 0
        return max(0, int(self.window - (time.monotonic() - events[0])) + 1)


login_attempts = SlidingWindow(LIMIT_LOGIN, WINDOW_LOGIN)
registrations = SlidingWindow(LIMIT_REGISTER, WINDOW_REGISTER)
api_requests = SlidingWindow(LIMIT_API, WINDOW_API)
# Повторная отправка письма и запрос восстановления — не чаще 1 раза в минуту
email_requests = SlidingWindow(1, 60)


def client_ip(request) -> str:
    """IP клиента с учётом обратного прокси (Caddy передаёт X-Forwarded-For)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
