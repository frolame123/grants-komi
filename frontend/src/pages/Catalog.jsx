/**
 * Каталог программ (FR-004).
 *
 * Фильтры и страница хранятся в адресной строке: ссылку на отфильтрованную
 * выдачу можно отправить коллеге, а кнопка «назад» в браузере возвращает
 * прежний набор условий.
 */

import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { api, withQuery } from "../api/client";
import ProgramCard from "../components/ProgramCard";

const APPLICANT_TYPES = [
  ["", "Любой заявитель"],
  ["IP", "Индивидуальный предприниматель"],
  ["OOO", "Общество с ограниченной ответственностью"],
  ["NKO", "Некоммерческая организация"],
  ["SMZ", "Самозанятый"],
];

const SORTS = [
  ["deadline:asc", "Сначала ближайший срок"],
  ["deadline:desc", "Сначала дальний срок"],
  ["amount:desc", "Сначала крупная сумма"],
  ["amount:asc", "Сначала небольшая сумма"],
];

export default function Catalog({ archive = false }) {
  const [params, setParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [categories, setCategories] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const page = Number(params.get("page") ?? 1);
  const search = params.get("search") ?? "";
  const [sortField, sortOrder] = (params.get("sort") ?? "deadline:asc").split(":");

  useEffect(() => {
    if (!archive) api.get("/api/categories").then(setCategories).catch(() => setCategories([]));
  }, [archive]);

  useEffect(() => {
    setLoading(true);
    setError(null);

    const path = archive
      ? withQuery("/api/programs/archive", { search, page })
      : withQuery("/api/programs", {
          search,
          page,
          category_id: params.get("category_id"),
          applicant_type: params.get("applicant_type"),
          amount_min: params.get("amount_min"),
          amount_max: params.get("amount_max"),
          deadline_before: params.get("deadline_before"),
          sort: sortField,
          order: sortOrder,
        });

    api
      .get(path)
      .then(setData)
      .catch((exception) => setError(exception.message))
      .finally(() => setLoading(false));
  }, [archive, params, page, search, sortField, sortOrder]);

  function change(field, value) {
    const next = new URLSearchParams(params);
    if (value) next.set(field, value);
    else next.delete(field);
    if (field !== "page") next.delete("page"); // смена фильтров возвращает к первой странице
    setParams(next);
  }

  function reset() {
    setParams(new URLSearchParams());
  }

  const pages = data ? Math.ceil(data.total / data.page_size) : 0;

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-xl font-semibold">
          {archive ? "Завершённые конкурсы" : "Каталог программ поддержки"}
        </h1>
        <Link
          to={archive ? "/programs" : "/archive"}
          className="text-sm text-ink-soft hover:text-ink hover:underline"
        >
          {archive ? "К действующим программам" : "Завершённые конкурсы"}
        </Link>
      </div>

      <form
        className="mb-6 grid gap-3 rounded border border-line bg-surface p-4 sm:grid-cols-2 lg:grid-cols-4"
        onSubmit={(event) => event.preventDefault()}
        role="search"
      >
        <label className="sm:col-span-2 lg:col-span-4">
          <span className="mb-1 block text-sm">Поиск по названию и организатору</span>
          <input
            type="search"
            className="field"
            defaultValue={search}
            maxLength={100}
            placeholder="Например: грант социальное предпринимательство"
            onBlur={(event) => change("search", event.target.value.trim())}
            onKeyDown={(event) => {
              if (event.key === "Enter") change("search", event.target.value.trim());
            }}
          />
        </label>

        {!archive && (
          <>
            <label>
              <span className="mb-1 block text-sm">Категория</span>
              <select
                className="field"
                value={params.get("category_id") ?? ""}
                onChange={(event) => change("category_id", event.target.value)}
              >
                <option value="">Любая категория</option>
                {categories.map((category) => (
                  <option key={category.category_id} value={category.category_id}>
                    {category.name}
                  </option>
                ))}
              </select>
            </label>

            <label>
              <span className="mb-1 block text-sm">Тип заявителя</span>
              <select
                className="field"
                value={params.get("applicant_type") ?? ""}
                onChange={(event) => change("applicant_type", event.target.value)}
              >
                {APPLICANT_TYPES.map(([value, title]) => (
                  <option key={value} value={value}>
                    {title}
                  </option>
                ))}
              </select>
            </label>

            <label>
              <span className="mb-1 block text-sm">Сумма не менее, ₽</span>
              <input
                type="number"
                min="0"
                step="50000"
                className="field"
                defaultValue={params.get("amount_min") ?? ""}
                onBlur={(event) => change("amount_min", event.target.value)}
              />
            </label>

            <label>
              <span className="mb-1 block text-sm">Приём заканчивается до</span>
              <input
                type="date"
                className="field"
                defaultValue={params.get("deadline_before") ?? ""}
                onChange={(event) => change("deadline_before", event.target.value)}
              />
            </label>

            <label className="lg:col-span-2">
              <span className="mb-1 block text-sm">Сортировка</span>
              <select
                className="field"
                value={`${sortField}:${sortOrder}`}
                onChange={(event) => change("sort", event.target.value)}
              >
                {SORTS.map(([value, title]) => (
                  <option key={value} value={value}>
                    {title}
                  </option>
                ))}
              </select>
            </label>

            <div className="flex items-end lg:col-span-2">
              <button type="button" className="btn-secondary" onClick={reset}>
                Сбросить фильтры
              </button>
            </div>
          </>
        )}
      </form>

      {loading && <p className="text-sm text-ink-soft">Загружаем каталог…</p>}

      {error && (
        <p role="alert" className="rounded border border-alert/40 bg-alert/5 px-3 py-2 text-sm text-alert">
          {error}
        </p>
      )}

      {data && !loading && (
        <>
          <p className="mb-4 text-sm text-ink-soft">
            Найдено программ: {data.total}
          </p>

          {data.items.length === 0 ? (
            <div className="rounded border border-line p-8 text-center">
              <p className="mb-3">Ничего не найдено</p>
              <button type="button" className="btn-secondary" onClick={reset}>
                Сбросить фильтры
              </button>
            </div>
          ) : (
            <ul className="grid gap-4 md:grid-cols-2">
              {data.items.map((program) => (
                <li key={program.program_id}>
                  <ProgramCard program={program} />
                </li>
              ))}
            </ul>
          )}

          {pages > 1 && (
            <nav className="mt-6 flex items-center justify-center gap-2" aria-label="Страницы">
              <button
                type="button"
                className="btn-secondary"
                disabled={page <= 1}
                onClick={() => change("page", String(page - 1))}
              >
                Назад
              </button>
              <span className="text-sm text-ink-soft">
                Страница {page} из {pages}
              </span>
              <button
                type="button"
                className="btn-secondary"
                disabled={page >= pages}
                onClick={() => change("page", String(page + 1))}
              >
                Вперёд
              </button>
            </nav>
          )}
        </>
      )}
    </div>
  );
}
