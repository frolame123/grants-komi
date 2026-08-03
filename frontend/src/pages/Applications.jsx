/**
 * Мои заявки: статусная модель FR-008.
 *
 * Интерфейс показывает ровно один доступный переход — тот, что разрешает
 * конечный автомат на сервере. Кнопок «назад» нет, потому что таких переходов
 * не существует: заявка движется только вперёд.
 */

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import { formatDate } from "../components/ProgramCard";
import { useToast } from "../components/Toast";

const NEXT_STEP = {
  DRAFT: { status: "PREP", label: "Начать подготовку" },
  PREP: { status: "SENT", label: "Отметить поданной" },
};

const RESULTS = [
  ["APPROVED", "Одобрена"],
  ["REJECTED", "Отклонена"],
];

const STATUS_STYLES = {
  DRAFT: "bg-surface text-ink-soft",
  PREP: "bg-surface text-ink",
  SENT: "bg-ink text-white",
  RES: "bg-success/10 text-success",
};

export default function Applications() {
  const toast = useToast();
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(() => {
    api
      .get("/api/applications")
      .then(setItems)
      .catch((exception) => setError(exception.message));
  }, []);

  useEffect(load, [load]);

  async function move(application, status, result = null) {
    setBusyId(application.application_id);
    try {
      await api.patch(`/api/applications/${application.application_id}`, { status, result });
      toast.success("Статус заявки обновлён");
      load();
    } catch (exception) {
      toast.error(exception.message);
    } finally {
      setBusyId(null);
    }
  }

  async function remove(application) {
    setBusyId(application.application_id);
    try {
      await api.delete(`/api/applications/${application.application_id}`);
      toast.success("Заявка удалена");
      load();
    } catch (exception) {
      toast.error(exception.message);
    } finally {
      setBusyId(null);
    }
  }

  if (error) {
    return (
      <p role="alert" className="rounded border border-alert/40 bg-alert/5 px-3 py-2 text-sm text-alert">
        {error}
      </p>
    );
  }

  if (!items) return <p className="text-sm text-ink-soft">Загружаем заявки…</p>;

  return (
    <div>
      <h1 className="mb-2 text-xl font-semibold">Мои заявки</h1>
      <p className="mb-6 text-sm text-ink-soft">
        Заявка подаётся на площадке организатора. Здесь вы отмечаете, на каком
        этапе находитесь, и видите историю.
      </p>

      {items.length === 0 ? (
        <div className="rounded border border-line p-8 text-center">
          <p className="mb-3 text-sm">Заявок пока нет.</p>
          <Link to="/programs" className="btn-secondary">
            Выбрать программу
          </Link>
        </div>
      ) : (
        <ul className="space-y-4">
          {items.map((application) => {
            const step = NEXT_STEP[application.status];
            const busy = busyId === application.application_id;

            return (
              <li
                key={application.application_id}
                id={String(application.application_id)}
                className="rounded border border-line p-4"
              >
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <span
                    className={`rounded px-2 py-0.5 text-xs ${STATUS_STYLES[application.status]}`}
                  >
                    {application.status_name}
                  </span>
                  {application.result && (
                    <span className="text-xs text-ink-soft">
                      результат: {application.result === "APPROVED" ? "одобрена" : "отклонена"}
                    </span>
                  )}
                  {application.program_archived && (
                    <span className="text-xs text-warning">программа завершена</span>
                  )}
                  <span className="ml-auto text-xs text-ink-soft">
                    изменена {formatDate(application.status_date)}
                  </span>
                </div>

                <h2 className="mb-3 text-base font-medium">
                  <Link to={`/programs/${application.program_id}`} className="hover:underline">
                    {application.program_title}
                  </Link>
                </h2>

                <div className="mb-3 flex flex-wrap gap-2">
                  {step && !application.program_archived && (
                    <button
                      type="button"
                      className="btn-primary"
                      disabled={busy}
                      onClick={() => move(application, step.status)}
                    >
                      {step.label}
                    </button>
                  )}

                  {application.status !== "RES" &&
                    (application.status === "SENT" || application.program_archived) &&
                    RESULTS.map(([value, title]) => (
                      <button
                        key={value}
                        type="button"
                        className="btn-secondary"
                        disabled={busy}
                        onClick={() => move(application, "RES", value)}
                      >
                        {title}
                      </button>
                    ))}

                  {application.status !== "RES" && (
                    <button
                      type="button"
                      className="btn-secondary"
                      disabled={busy}
                      onClick={() => remove(application)}
                    >
                      Удалить
                    </button>
                  )}
                </div>

                <details className="text-sm">
                  <summary className="cursor-pointer text-ink-soft hover:text-ink">
                    История переходов ({application.history.length})
                  </summary>
                  <ol className="mt-2 space-y-1 border-l border-line pl-4">
                    {application.history.map((record, index) => (
                      <li key={index} className="text-xs text-ink-soft">
                        {new Date(record.created_at).toLocaleString("ru-RU")} —{" "}
                        <span className="text-ink">{record.status_name}</span>
                        {record.comment && `: ${record.comment}`}
                      </li>
                    ))}
                  </ol>
                </details>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
