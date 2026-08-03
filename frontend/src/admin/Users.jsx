/**
 * Управление пользователями (FR-012).
 *
 * Администратор не может изменить собственную роль или заблокировать себя:
 * запрет проверяет сервер, а интерфейс не показывает такие действия — чтобы
 * не предлагать то, что заведомо отклонят.
 */

import { useCallback, useEffect, useState } from "react";

import { api, withQuery } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toast";

const ROLES = [
  ["applicant", "Заявитель"],
  ["moderator", "Контент-менеджер"],
  ["admin", "Администратор"],
];

const STATUS_FILTER = [
  ["", "Любое состояние"],
  ["active", "Активные"],
  ["pending", "Не подтверждённые"],
  ["blocked", "Заблокированные"],
];

export default function Users() {
  const { user: current } = useAuth();
  const toast = useToast();

  const [filters, setFilters] = useState({ search: "", role: "", status: "" });
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(() => {
    api.get(withQuery("/api/admin/users", { ...filters, page })).then(setData).catch(() => setData(null));
  }, [filters, page]);

  useEffect(load, [load]);

  async function act(userId, action) {
    setBusyId(userId);
    try {
      await action();
      load();
    } catch (exception) {
      toast.error(exception.message);
    } finally {
      setBusyId(null);
    }
  }

  const changeRole = (row, role) =>
    act(row.user_id, async () => {
      await api.patch(`/api/admin/users/${row.user_id}/role`, { role });
      toast.success(`Роль изменена на «${ROLES.find(([v]) => v === role)[1]}»`);
    });

  const changeStatus = (row, status) =>
    act(row.user_id, async () => {
      await api.patch(`/api/admin/users/${row.user_id}/status`, { status });
      toast.success(status === "blocked" ? "Учётная запись заблокирована" : "Блокировка снята");
    });

  const resetPassword = (row) =>
    act(row.user_id, async () => {
      await api.post(`/api/admin/users/${row.user_id}/password-reset`);
      toast.success("Ссылка для смены пароля отправлена пользователю");
    });

  const pages = data ? Math.ceil(data.total / data.page_size) : 0;

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold">Пользователи</h1>

      <form
        className="mb-6 grid gap-3 rounded border border-line bg-surface p-4 sm:grid-cols-3"
        onSubmit={(event) => event.preventDefault()}
      >
        <label>
          <span className="mb-1 block text-sm">Поиск по адресу</span>
          <input
            type="search"
            className="field"
            defaultValue={filters.search}
            onBlur={(event) => {
              setPage(1);
              setFilters({ ...filters, search: event.target.value.trim() });
            }}
          />
        </label>

        <label>
          <span className="mb-1 block text-sm">Роль</span>
          <select
            className="field"
            value={filters.role}
            onChange={(event) => {
              setPage(1);
              setFilters({ ...filters, role: event.target.value });
            }}
          >
            <option value="">Любая роль</option>
            {ROLES.map(([value, title]) => (
              <option key={value} value={value}>
                {title}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span className="mb-1 block text-sm">Состояние</span>
          <select
            className="field"
            value={filters.status}
            onChange={(event) => {
              setPage(1);
              setFilters({ ...filters, status: event.target.value });
            }}
          >
            {STATUS_FILTER.map(([value, title]) => (
              <option key={value} value={value}>
                {title}
              </option>
            ))}
          </select>
        </label>
      </form>

      {!data && <p className="text-sm text-ink-soft">Загружаем список…</p>}

      {data && (
        <>
          <p className="mb-3 text-sm text-ink-soft">Найдено: {data.total}</p>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[46rem] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs text-ink-soft">
                  <th className="py-2 pr-3 font-normal">Адрес</th>
                  <th className="py-2 pr-3 font-normal">Роль</th>
                  <th className="py-2 pr-3 font-normal">Состояние</th>
                  <th className="py-2 pr-3 font-normal">Последняя активность</th>
                  <th className="py-2 font-normal">Действия</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((row) => {
                  const self = row.user_id === current?.user_id;
                  const busy = busyId === row.user_id;

                  return (
                    <tr key={row.user_id} className="border-b border-line/60 align-top">
                      <td className="py-2 pr-3">
                        {row.email}
                        {row.deleted && (
                          <span className="ml-1 text-xs text-ink-soft">(удалена)</span>
                        )}
                        {self && <span className="ml-1 text-xs text-ink-soft">(вы)</span>}
                        {row.has_profile && (
                          <span className="mt-0.5 block text-xs text-ink-soft">профиль заполнен</span>
                        )}
                      </td>

                      <td className="py-2 pr-3">
                        {self || row.deleted ? (
                          row.role_name
                        ) : (
                          <select
                            className="field py-1 text-xs"
                            value={row.role}
                            disabled={busy}
                            onChange={(event) => changeRole(row, event.target.value)}
                            aria-label={`Роль пользователя ${row.email}`}
                          >
                            {ROLES.map(([value, title]) => (
                              <option key={value} value={value}>
                                {title}
                              </option>
                            ))}
                          </select>
                        )}
                      </td>

                      <td className="py-2 pr-3">{row.status_name}</td>

                      <td className="py-2 pr-3 text-ink-soft">
                        {row.last_active_at
                          ? new Date(row.last_active_at).toLocaleString("ru-RU")
                          : "не входил"}
                      </td>

                      <td className="py-2">
                        {!self && !row.deleted && (
                          <div className="flex flex-wrap gap-1">
                            <button
                              type="button"
                              className="btn-secondary px-2 py-1 text-xs"
                              disabled={busy}
                              onClick={() =>
                                changeStatus(row, row.status === "blocked" ? "active" : "blocked")
                              }
                            >
                              {row.status === "blocked" ? "Разблокировать" : "Заблокировать"}
                            </button>
                            <button
                              type="button"
                              className="btn-secondary px-2 py-1 text-xs"
                              disabled={busy}
                              onClick={() => resetPassword(row)}
                            >
                              Сбросить пароль
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
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
