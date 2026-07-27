# Гранты Коми

Информационная система агрегации и интеллектуального подбора мер грантовой
поддержки для субъектов МСП и НКО Республики Коми (ТЗ, редакция 3).

Стек: FastAPI + SQLAlchemy + Alembic, PostgreSQL 16, React + Vite + Tailwind,
JWT, Docker, Caddy.

## Развёртывание

```bash
cp .env.example .env          # заполнить SECRET_KEY и пароль БД
docker compose up -d --build  # миграции применяются при старте backend
```

API: http://127.0.0.1:8000 — Swagger на `/docs` (алиас `/api-docs`).

Тестовые данные (по желанию, только для разработки):

```bash
docker compose exec -T db psql -U grants -d grants < backend/db/seed.sql
```

## Локальная разработка backend

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

## Схема БД

`backend/db/schema.sql` — единственный источник правды (версия 2, прошла
техническое ревью). Миграция `alembic/versions/0001_initial_schema.py`
выполняет этот скрипт; модели в `app/models.py` его отражают.

Проверка, что модели не разошлись со схемой:

```bash
cd backend && python check_models.py
```

## Структура

```
backend/
  app/        конфигурация, сессии БД, модели, точка входа API
  alembic/    миграции
  db/         schema.sql (DDL) и seed.sql (тестовые данные)
frontend/     клиентская часть (этап 4 ТЗ)
```
