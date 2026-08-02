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

Нужен установленный PostgreSQL 16. Создайте роль и базу:

```sql
CREATE USER grants WITH PASSWORD 'пароль';
CREATE DATABASE grants OWNER grants;
```

Скопируйте `.env.example` в `backend/.env`, укажите в нём строку подключения
и секретный ключ, затем:

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Тестовые данные (скрипт повторяемый, перед наполнением очищает таблицы):

```bash
psql -U grants -d grants -f db/schema.sql   # не нужно: схему создаёт alembic
psql -U grants -d grants -f db/seed.sql
```

## Проверки

```bash
cd backend
python check_models.py        # модели не разошлись со схемой
python check_auth.py          # пароли, токены, ограничение частоты запросов
python check_business.py      # контрольное число ИНН, подбор программ
python check_workflow.py      # статусная модель заявки
python check_admin.py         # правила администрирования
python check_dictionaries.py  # регламент справочников
python check_moderation.py    # сравнение «было / стало», правила модерации
python check_api.py           # сквозной сценарий против работающей СУБД
python db/explain_report.py   # планы выполнения запросов и работа индексов
```

Первые семь проверок работают без базы данных. `check_api.py` и
`explain_report.py` требуют поднятой СУБД с применёнными миграциями.

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
