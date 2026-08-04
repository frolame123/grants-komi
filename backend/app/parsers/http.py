"""Загрузка страниц источников (FR-006).

Два обстоятельства, из-за которых обычного HTTP-клиента недостаточно.

Первое: часть государственных сайтов использует сертификаты национального
удостоверяющего центра Минцифры, которого нет в наборе доверенных корневых
сертификатов, поставляемом с Python. Правильное решение — расширить набор,
добавив к нему эти корневые сертификаты. Отключать проверку нельзя: тогда
подмена содержимого источника перестанет обнаруживаться, а система выдаёт
эти сведения пользователям как достоверные.

Второе: п. 4.2.6 ТЗ требует до трёх повторных попыток при сетевой ошибке или
коде ответа 5xx, после чего прогон помечается неуспешным и данные не
изменяются.
"""

import asyncio
import logging
import ssl
from pathlib import Path

import certifi
import httpx

log = logging.getLogger(__name__)

CERTS_DIR = Path(__file__).resolve().parents[2] / "certs"
BUNDLE_PATH = CERTS_DIR / "bundle.pem"

# Заголовки HTTP передаются в кодировке ASCII, поэтому строка только латиницей
USER_AGENT = "GrantyKomiBot/1.0 (+https://github.com/frolame123/grants-komi)"

REQUEST_TIMEOUT = 30
MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 600  # 10 минут между попытками (п. 4.2.6 ТЗ)


def build_bundle() -> Path:
    """Набор доверенных корневых сертификатов: общемировой плюс российский.

    Файл собирается один раз и переиспользуется. Если корневых сертификатов
    Минцифры в проекте нет, возвращается стандартный набор — часть источников
    при этом окажется недоступна, что честно отразится в логе прогонов.
    """
    extra = sorted(CERTS_DIR.glob("russian_trusted_*.crt"))
    if not extra:
        return Path(certifi.where())

    if not BUNDLE_PATH.exists():
        parts = [Path(certifi.where()).read_text(encoding="utf-8")]
        parts += [path.read_text(encoding="utf-8") for path in extra]
        BUNDLE_PATH.write_text("\n".join(parts), encoding="utf-8")
        log.info("Собран набор сертификатов: %s", BUNDLE_PATH)

    return BUNDLE_PATH


def ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=str(build_bundle()))


def create_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
        verify=ssl_context(),
    )


async def fetch(client: httpx.AsyncClient, url: str, delay: int = RETRY_DELAY_SECONDS) -> str:
    """Загрузка страницы с повторными попытками (п. 4.2.6 ТЗ).

    Повтор выполняется при сетевой ошибке и при ответе 5xx — это признаки
    временной неисправности источника. Ответы 4xx не повторяются: страницы
    просто нет, и через десять минут она не появится.
    """
    last_error: Exception | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = await client.get(url)
            if response.status_code >= 500:
                raise httpx.HTTPStatusError(
                    f"код ответа {response.status_code}",
                    request=response.request,
                    response=response,
                )
            response.raise_for_status()
            return response.text
        except (httpx.HTTPError, ssl.SSLError) as exc:
            last_error = exc
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500:
                break
            log.warning("Попытка %s из %s не удалась: %s", attempt, MAX_ATTEMPTS, exc)
            if attempt < MAX_ATTEMPTS:
                await asyncio.sleep(delay)

    raise RuntimeError(f"Источник недоступен после {MAX_ATTEMPTS} попыток: {last_error}")
