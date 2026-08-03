/**
 * Сводка панели управления: счётчики, графики, состояние источников.
 *
 * Данные обновляются при возврате на вкладку и раз в минуту: сводка должна
 * показывать текущее положение дел, но опрашивать сервер чаще незачем —
 * счётчики так быстро не меняются.
 */

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import BarChart, { BarList } from "../components/BarChart";

const REFRESH_MS = 60_000;

const RUN_STYLES = {
  success: "text-success",
  failed: "text-alert",
  discarded: "text-warning",
};

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    api
      .get("/api/admin/stats")
      .then(setData)
      .catch((exception) => setError(exception.message));
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, REFRESH_MS);
    const onFocus = () => load();
    window.addEventListener("focus", onFocus);
    return () => {
      clearInterval(timer);
      window.removeEventListener("focus", onFocus);
    };
  }, [load]);

  if (error) {
    return (
      <p role="alert" className="rounded border border-alert/40 bg-alert/5 px-3 py-2 text-sm text-alert">
        {error}
      </p>
    );
  }

  if (!data) return <p className="text-sm text-ink-soft">Загружаем сводку…</p>;

  const { counters } = data;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="mb-4 text-xl font-semibold">Сводка</h1>
        <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Counter label="Пользователей" value={counters.users_total} note={`активных ${counters.users_active}`} />
          <Counter label="Новых за месяц" value={counters.users_new_month} />
          <Counter
            label="Программ опубликовано"
            value={counters.programs_published}
            note={`всего ${counters.programs_total}`}
          />
          <Counter
            label="Заявок"
            value={counters.applications_total}
            note={`активных ${counters.applications_active}`}
          />
        </dl>
      </div>

      {counters.moderation_waiting > 0 && (
        <p className="rounded border border-line bg-surface px-4 py-3 text-sm">
          В очереди модерации ждут рассмотрения записей: {counters.moderation_waiting}.{" "}
          <Link to="/admin/moderation" className="underline">
            Перейти к очереди
          </Link>
        </p>
      )}

      <BarChart points={data.registrations} caption="Регистрации по дням" />

      <div className="grid gap-6 lg:grid-cols-3">
        <BarList points={data.programs_by_status} caption="Программы по статусам" />
        <BarList points={data.applications_by_status} caption="Заявки по статусам" />
        <BarList points={data.users_by_role} caption="Пользователи по ролям" />
      </div>

      <section>
        <h2 className="mb-2 text-base font-medium">Источники агрегации</h2>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[36rem] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs text-ink-soft">
                <th className="py-2 pr-3 font-normal">Источник</th>
                <th className="py-2 pr-3 font-normal">Опрос</th>
                <th className="py-2 pr-3 font-normal">Последний прогон</th>
                <th className="py-2 pr-3 font-normal">Итог</th>
                <th className="py-2 font-normal">Новых</th>
              </tr>
            </thead>
            <tbody>
              {data.sources.map((source) => (
                <tr key={source.source_id} className="border-b border-line/60 align-top">
                  <td className="py-2 pr-3">{source.source_name}</td>
                  <td className="py-2 pr-3 text-ink-soft">
                    {source.schedule === "daily" ? "ежесуточно" : "еженедельно"}
                  </td>
                  <td className="py-2 pr-3 text-ink-soft">
                    {source.last_run_at
                      ? new Date(source.last_run_at).toLocaleString("ru-RU")
                      : "не опрашивался"}
                  </td>
                  <td className={`py-2 pr-3 ${RUN_STYLES[source.last_status] ?? ""}`}>
                    {source.last_status ?? "—"}
                    {source.last_message && (
                      <span className="mt-0.5 block max-w-md text-xs text-ink-soft">
                        {source.last_message}
                      </span>
                    )}
                  </td>
                  <td className="py-2 tabular-nums">{source.new_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function Counter({ label, value, note }) {
  return (
    <div className="rounded border border-line p-4">
      <dt className="text-xs text-ink-soft">{label}</dt>
      <dd className="text-2xl font-semibold tabular-nums">{value}</dd>
      {note && <dd className="text-xs text-ink-soft">{note}</dd>}
    </div>
  );
}
