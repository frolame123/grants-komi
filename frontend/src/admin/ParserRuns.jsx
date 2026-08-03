/**
 * Прогоны агрегации (FR-006).
 *
 * Кроме истории прогонов даёт внеочередной запуск источника: ждать ночного
 * расписания при проверке или демонстрации незачем.
 */

import { useCallback, useEffect, useState } from "react";

import { api } from "../api/client";
import { useToast } from "../components/Toast";

const STATUS_STYLES = {
  success: "text-success",
  failed: "text-alert",
  discarded: "text-warning",
};

export default function ParserRuns() {
  const toast = useToast();
  const [runs, setRuns] = useState(null);
  const [sources, setSources] = useState([]);
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(() => {
    api.get("/api/admin/parser-runs").then(setRuns).catch(() => setRuns([]));
    api
      .get("/api/admin/stats")
      .then((stats) => setSources(stats.sources))
      .catch(() => setSources([]));
  }, []);

  useEffect(load, [load]);

  async function run(source) {
    setBusyId(source.source_id);
    try {
      const result = await api.post(`/api/admin/parser-runs/${source.source_id}/run`);
      if (result.status === "success") {
        toast.success(
          `Прогон завершён: новых ${result.new_count}, изменённых ${result.updated_count}`,
        );
      } else {
        toast.error(`Прогон не выполнен: ${result.message ?? result.status}`);
      }
      load();
    } catch (exception) {
      toast.error(exception.message);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div>
      <h1 className="mb-2 text-xl font-semibold">Прогоны агрегации</h1>
      <p className="mb-6 text-sm text-ink-soft">
        Источники опрашиваются по расписанию: ежесуточные — ночью, еженедельные —
        по понедельникам. Внеочередной запуск нужен для проверки и демонстрации.
      </p>

      <section className="mb-8">
        <h2 className="mb-2 text-base font-medium">Источники</h2>
        <ul className="space-y-2">
          {sources.map((source) => (
            <li
              key={source.source_id}
              className="flex flex-wrap items-center gap-3 rounded border border-line p-3"
            >
              <span className="text-sm">{source.source_name}</span>
              <span className="text-xs text-ink-soft">
                {source.schedule === "daily" ? "ежесуточно" : "еженедельно"}
              </span>
              <button
                type="button"
                className="btn-secondary ml-auto px-3 py-1 text-xs"
                disabled={busyId === source.source_id}
                onClick={() => run(source)}
              >
                {busyId === source.source_id ? "Опрашиваем…" : "Опросить сейчас"}
              </button>
            </li>
          ))}
        </ul>
      </section>

      <h2 className="mb-2 text-base font-medium">История прогонов</h2>

      {!runs && <p className="text-sm text-ink-soft">Загружаем историю…</p>}

      {runs && runs.length === 0 && (
        <p className="rounded border border-line p-8 text-center text-sm text-ink-soft">
          Прогонов ещё не было.
        </p>
      )}

      {runs && runs.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[46rem] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs text-ink-soft">
                <th className="py-2 pr-3 font-normal">Начало</th>
                <th className="py-2 pr-3 font-normal">Источник</th>
                <th className="py-2 pr-3 font-normal">Итог</th>
                <th className="py-2 pr-3 font-normal">Новых</th>
                <th className="py-2 pr-3 font-normal">Изменённых</th>
                <th className="py-2 font-normal">Пояснение</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((row) => (
                <tr key={row.run_id} className="border-b border-line/60 align-top">
                  <td className="py-2 pr-3 whitespace-nowrap text-ink-soft">
                    {new Date(row.started_at).toLocaleString("ru-RU")}
                  </td>
                  <td className="py-2 pr-3">{row.source_name}</td>
                  <td className={`py-2 pr-3 ${STATUS_STYLES[row.status] ?? ""}`}>
                    {row.status_name}
                  </td>
                  <td className="py-2 pr-3 tabular-nums">{row.new_count}</td>
                  <td className="py-2 pr-3 tabular-nums">{row.updated_count}</td>
                  <td className="py-2 text-xs text-ink-soft">{row.message ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
