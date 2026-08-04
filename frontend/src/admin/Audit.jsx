/**
 * Журнал аудита (FR-015).
 *
 * Только чтение: изменять и удалять записи нельзя, иначе журнал перестаёт
 * быть доказательством. Кнопок правки нет и на сервере таких маршрутов тоже.
 */

import { useCallback, useEffect, useState } from "react";

import { api, withQuery } from "../api/client";

export default function Audit() {
  const [actions, setActions] = useState({});
  const [filters, setFilters] = useState({ action: "", date_from: "", date_to: "" });
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get("/api/admin/audit/actions").then(setActions).catch(() => setActions({}));
  }, []);

  const load = useCallback(() => {
    api.get(withQuery("/api/admin/audit", { ...filters, page })).then(setData).catch(() => setData(null));
  }, [filters, page]);

  useEffect(load, [load]);

  const pages = data ? Math.ceil(data.total / data.page_size) : 0;

  return (
    <div>
      <h1 className="mb-2 text-xl font-semibold">Журнал аудита</h1>
      <p className="mb-6 text-sm text-ink-soft">
        Записи неизменяемы. Срок хранения — не менее года.
      </p>

      <form
        className="mb-6 grid gap-3 rounded border border-line bg-surface p-4 sm:grid-cols-3"
        onSubmit={(event) => event.preventDefault()}
      >
        <label>
          <span className="mb-1 block text-sm">Действие</span>
          <select
            className="field"
            value={filters.action}
            onChange={(event) => {
              setPage(1);
              setFilters({ ...filters, action: event.target.value });
            }}
          >
            <option value="">Все действия</option>
            {Object.entries(actions).map(([code, title]) => (
              <option key={code} value={code}>
                {title}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span className="mb-1 block text-sm">С даты</span>
          <input
            type="date"
            className="field"
            value={filters.date_from}
            onChange={(event) => {
              setPage(1);
              setFilters({ ...filters, date_from: event.target.value });
            }}
          />
        </label>

        <label>
          <span className="mb-1 block text-sm">По дату</span>
          <input
            type="date"
            className="field"
            value={filters.date_to}
            onChange={(event) => {
              setPage(1);
              setFilters({ ...filters, date_to: event.target.value });
            }}
          />
        </label>
      </form>

      {!data && <p className="text-sm text-ink-soft">Загружаем журнал…</p>}

      {data && (
        <>
          <p className="mb-3 text-sm text-ink-soft">Записей: {data.total}</p>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[46rem] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs text-ink-soft">
                  <th className="py-2 pr-3 font-normal">Время</th>
                  <th className="py-2 pr-3 font-normal">Действие</th>
                  <th className="py-2 pr-3 font-normal">Кто</th>
                  <th className="py-2 pr-3 font-normal">Объект</th>
                  <th className="py-2 pr-3 font-normal">Адрес</th>
                  <th className="py-2 font-normal">Подробности</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((row) => (
                  <tr key={row.audit_id} className="border-b border-line/60 align-top">
                    <td className="py-2 pr-3 whitespace-nowrap text-ink-soft">
                      {new Date(row.created_at).toLocaleString("ru-RU")}
                    </td>
                    <td className="py-2 pr-3">{row.action_name}</td>
                    <td className="py-2 pr-3">{row.user_email ?? "—"}</td>
                    <td className="py-2 pr-3 text-ink-soft">
                      {row.entity}
                      {row.entity_id ? ` №${row.entity_id}` : ""}
                    </td>
                    <td className="py-2 pr-3 text-ink-soft">{row.ip_address ?? "—"}</td>
                    <td className="py-2 text-xs text-ink-soft">{row.details ?? ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {pages > 1 && (
            <nav className="mt-4 flex items-center justify-center gap-2" aria-label="Страницы">
              <button
                type="button"
                className="btn-secondary"
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
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
                onClick={() => setPage(page + 1)}
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
