"""Точка входа REST API «Гранты Коми»."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from app.api import (
    account,
    admin,
    applications,
    audit_log,
    auth,
    dictionaries,
    moderation,
    notifications,
    profile,
    programs,
    stats,
)
from app.config import settings
from app.ratelimit import api_requests, client_ip
from app import scheduler

log = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(application: FastAPI):
    """Планировщик живёт вместе с приложением (FR-006, FR-011)."""
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(
    lifespan=lifespan,
    title="Гранты Коми — REST API",
    description=(
        "Информационная система агрегации и интеллектуального подбора мер "
        "грантовой поддержки для субъектов МСП и НКО Республики Коми"
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.public_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def limit_requests(request: Request, call_next):
    """Не более 100 запросов в минуту с одного IP-адреса (п. 4.1.4 ТЗ)."""
    if not api_requests.hit(client_ip(request)):
        return JSONResponse(
            {"detail": "Превышено допустимое число запросов, повторите попытку позже"},
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    return await call_next(request)


@app.exception_handler(404)
async def not_found(request: Request, exc) -> JSONResponse:
    return JSONResponse({"detail": "Страница не найдена"}, status_code=404)


@app.exception_handler(Exception)
async def internal_error(request: Request, exc: Exception) -> JSONResponse:
    """Внутренняя ошибка: подробности пишутся в журнал, наружу не выдаются."""
    log.exception("Необработанная ошибка при обработке %s", request.url.path)
    return JSONResponse(
        {"detail": "Технические работы. Попробуйте позже или свяжитесь с поддержкой"},
        status_code=500,
    )


app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(programs.router)
app.include_router(applications.router)
app.include_router(admin.router)
app.include_router(audit_log.router)
app.include_router(dictionaries.router)
app.include_router(moderation.router)
app.include_router(notifications.router)
app.include_router(account.router)
app.include_router(stats.router)


@app.get("/api-docs", include_in_schema=False)
def api_docs() -> RedirectResponse:
    """Алиас на Swagger: в SRS документация API указана по пути /api-docs."""
    return RedirectResponse("/docs")


@app.get("/api/health", tags=["служебные"])
def health() -> dict[str, str]:
    return {"status": "ok"}
