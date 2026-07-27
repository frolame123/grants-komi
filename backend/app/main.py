"""Точка входа REST API «Гранты Коми»."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.config import settings

app = FastAPI(
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


@app.get("/api-docs", include_in_schema=False)
def api_docs() -> RedirectResponse:
    """Алиас на Swagger: в SRS документация API указана по пути /api-docs."""
    return RedirectResponse("/docs")


@app.get("/api/health", tags=["служебные"])
def health() -> dict[str, str]:
    return {"status": "ok"}
