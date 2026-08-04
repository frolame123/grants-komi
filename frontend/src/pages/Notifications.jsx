/**
 * Уведомления о сроках (FR-011) и настройка рассылки.
 *
 * Отказ от писем не отключает уведомления в интерфейсе: они не покидают
 * систему и под требование о согласии на рассылку не подпадают (38-ФЗ).
 */

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, withQuery } from "../api/client";
import { formatDate } from "../components/ProgramCard";
import { useToast } from "../components/Toast";

export default function Notifications() {
  const toast = useToast();
  const [data, setData] = useState(null);
  const [settings, setSettings] = useState(null);
  const [unreadOnly, setUnreadOnly] = useState(false);

  const load = useCallback(() => {
    api.get(withQuery("/api/notifications", { unread_only: unreadOnly || undefined })).then(setData);
  }, [unreadOnly]);

  useEffect(load, [load]);
  useEffect(() => {
    api.get("/api/notifications/settings").then(setSettings).catch(() => setSettings(null));
  }, []);

  async function markRead(id) {
    await api.post(`/api/notifications/${id}/read`);
    load();
  }

  async function markAll() {
    await api.post("/api/notifications/read-all");
    toast.success("Все уведомления отмечены прочитанными");
    load();
  }

  async function toggleEmail(value) {
    const updated = await api.put("/api/notifications/settings", { email_notifications: value });
    setSettings(updated);
    toast.success(
      value ? "Письма о сроках включены" : "Письма отключены, уведомления останутся в системе",
    );
  }

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-6 text-xl font-semibold">Уведомления</h1>

      {settings && (
        <label className="mb-6 flex items-start gap-2 rounded border border-line bg-surface px-4 py-3 text-sm">
          <input
            type="checkbox"
            className="mt-0.5"
            checked={settings.email_notifications}
            onChange={(event) => toggleEmail(event.target.checked)}
          />
          <span>
            Присылать напоминания о сроках на электронную почту
            <span className="mt-0.5 block text-xs text-ink-soft">
              Уведомления в системе продолжат приходить в любом случае
            </span>
          </span>
        </label>
      )}

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={unreadOnly}
            onChange={(event) => setUnreadOnly(event.target.checked)}
          />
          Только непрочитанные
        </label>
        {data?.unread > 0 && (
          <button type="button" className="btn-secondary ml-auto" onClick={markAll}>
            Отметить все прочитанными
          </button>
        )}
      </div>

      {!data && <p className="text-sm text-ink-soft">Загружаем уведомления…</p>}

      {data && data.items.length === 0 && (
        <div className="rounded border border-line p-8 text-center text-sm">
          <p className="mb-3">Уведомлений нет.</p>
          <p className="text-ink-soft">
            Напоминания приходят за неделю и за день до окончания приёма по
            программам из избранного и активным заявкам.
          </p>
        </div>
      )}

      {data && data.items.length > 0 && (
        <ul className="space-y-2">
          {data.items.map((item) => (
            <li
              key={item.notification_id}
              className={`rounded border p-4 ${
                item.is_read ? "border-line" : "border-ink bg-surface"
              }`}
            >
              <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-ink-soft">
                <span className="rounded bg-white px-2 py-0.5">{item.type_name}</span>
                <span>приём до {formatDate(item.deadline)}</span>
                <span className="ml-auto">
                  {new Date(item.sent_at).toLocaleString("ru-RU")}
                </span>
              </div>

              <Link
                to={`/programs/${item.program_id}`}
                className="text-sm font-medium hover:underline"
              >
                {item.program_title}
              </Link>

              {!item.is_read && (
                <div className="mt-2">
                  <button
                    type="button"
                    className="text-xs text-ink-soft hover:text-ink hover:underline"
                    onClick={() => markRead(item.notification_id)}
                  >
                    Отметить прочитанным
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
