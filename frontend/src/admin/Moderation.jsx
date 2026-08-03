/**
 * Очередь модерации (FR-007).
 *
 * Каждая запись показывает представление «было / стало»: что именно
 * изменилось у карточки, с пометкой существенных полей. Отклонение требует
 * причины — поле обязательно, как и на сервере.
 */

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, withQuery } from "../api/client";
import { useToast } from "../components/Toast";

const STATUSES = [
  ["waiting", "Ожидают рассмотрения"],
  ["approved", "Опубликованные"],
  ["rejected", "Отклонённые"],
];

const CHANGE_TYPES = { NEW: "новая карточка", UPD: "изменение" };

export default function Moderation() {
  const toast = useToast();
  const [status, setStatus] = useState("waiting");
  const [data, setData] = useState(null);
  const [reasons, setReasons] = useState({});
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(() => {
    api.get(withQuery("/api/admin/moderation", { status })).then(setData).catch(() => setData(null));
  }, [status]);

  useEffect(load, [load]);

  async function publish(entry) {
    setBusyId(entry.queue_id);
    try {
      await api.post(`/api/admin/moderation/${entry.queue_id}/publish`);
      toast.success("Карточка опубликована");
      load();
    } catch (exception) {
      toast.error(exception.message);
    } finally {
      setBusyId(null);
    }
  }

  async function reject(entry) {
    const reason = (reasons[entry.queue_id] ?? "").trim();
    if (!reason) {
      toast.error("Укажите причину отклонения");
      return;
    }
    setBusyId(entry.queue_id);
    try {
      await api.post(`/api/admin/moderation/${entry.queue_id}/reject`, { reason });
      toast.success("Запись отклонена, прежнее содержимое восстановлено");
      load();
    } catch (exception) {
      toast.error(exception.message);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold">Очередь модерации</h1>

      <div className="mb-6 flex flex-wrap gap-1">
        {STATUSES.map(([value, title]) => (
          <button
            key={value}
            type="button"
            onClick={() => setStatus(value)}
            className={status === value ? "btn-primary" : "btn-secondary"}
          >
            {title}
          </button>
        ))}
      </div>

      {!data && <p className="text-sm text-ink-soft">Загружаем очередь…</p>}

      {data && data.items.length === 0 && (
        <p className="rounded border border-line p-8 text-center text-sm text-ink-soft">
          Записей нет.
        </p>
      )}

      {data && data.items.length > 0 && (
        <ul className="space-y-4">
          {data.items.map((entry) => (
            <li key={entry.queue_id} className="rounded border border-line p-4">
              <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-ink-soft">
                <span className="rounded bg-surface px-2 py-0.5">
                  {CHANGE_TYPES[entry.change_type] ?? entry.change_type}
                </span>
                <span>{entry.status_name}</span>
                <span className="ml-auto">
                  {new Date(entry.created_at).toLocaleString("ru-RU")}
                </span>
              </div>

              <h2 className="mb-1 text-base font-medium">
                <Link to={`/admin/programs/${entry.program_id}`} className="hover:underline">
                  {entry.program_title}
                </Link>
              </h2>
              <p className="mb-3 text-xs text-ink-soft">
                состояние карточки: {entry.program_status}
              </p>

              {entry.changes.length > 0 && <Changes changes={entry.changes} />}

              {entry.reason && (
                <p className="mb-3 rounded border border-line bg-surface px-3 py-2 text-sm">
                  Причина отклонения: {entry.reason}
                </p>
              )}

              {entry.status === "waiting" && (
                <div className="flex flex-wrap items-start gap-2">
                  <button
                    type="button"
                    className="btn-primary"
                    disabled={busyId === entry.queue_id}
                    onClick={() => publish(entry)}
                  >
                    Опубликовать
                  </button>

                  <input
                    className="field max-w-sm flex-1"
                    placeholder="Причина отклонения"
                    maxLength={300}
                    value={reasons[entry.queue_id] ?? ""}
                    onChange={(event) =>
                      setReasons({ ...reasons, [entry.queue_id]: event.target.value })
                    }
                    aria-label="Причина отклонения"
                  />
                  <button
                    type="button"
                    className="btn-secondary"
                    disabled={busyId === entry.queue_id}
                    onClick={() => reject(entry)}
                  >
                    Отклонить
                  </button>

                  <Link to={`/admin/programs/${entry.program_id}`} className="btn-secondary">
                    Дозаполнить
                  </Link>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Changes({ changes }) {
  return (
    <div className="mb-3 overflow-x-auto">
      <table className="w-full min-w-[30rem] text-sm">
        <caption className="mb-1 text-left text-xs text-ink-soft">
          Изменения: было и стало
        </caption>
        <thead>
          <tr className="border-b border-line text-left text-xs text-ink-soft">
            <th className="py-1 pr-3 font-normal">Поле</th>
            <th className="py-1 pr-3 font-normal">Было</th>
            <th className="py-1 font-normal">Стало</th>
          </tr>
        </thead>
        <tbody>
          {changes.map((change) => (
            <tr key={change.field} className="border-b border-line/60 align-top">
              <td className="py-1 pr-3">
                {change.field_name}
                {change.significant && (
                  <span className="ml-1 text-xs text-warning" title="существенное изменение">
                    ●
                  </span>
                )}
              </td>
              <td className="py-1 pr-3 text-ink-soft line-through decoration-line">
                {format(change.before)}
              </td>
              <td className="py-1">{format(change.after)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function format(value) {
  if (value === null || value === undefined || value === "") return "—";
  return Array.isArray(value) ? value.join(", ") : String(value);
}
