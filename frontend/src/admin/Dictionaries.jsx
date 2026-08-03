/**
 * Справочники (FR-016).
 *
 * Значения не удаляются: дубли объединяются с переносом всех ссылок. Кнопки
 * удаления в интерфейсе нет вовсе — иначе она обещала бы действие, которого
 * система не выполняет.
 */

import { useCallback, useEffect, useState } from "react";

import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toast";

const STATUS_STYLES = {
  proposed: "bg-warning/10 text-warning",
  approved: "bg-surface text-ink-soft",
  merged: "bg-surface text-ink-soft line-through",
};

export default function Dictionaries() {
  const { isAdmin } = useAuth();
  const toast = useToast();

  const [items, setItems] = useState(null);
  const [name, setName] = useState("");
  const [mergeInto, setMergeInto] = useState({});
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api
      .get("/api/admin/dictionaries/categories")
      .then(setItems)
      .catch(() => setItems([]));
  }, []);

  useEffect(load, [load]);

  async function run(action, success) {
    setBusy(true);
    try {
      await action();
      toast.success(success);
      load();
    } catch (exception) {
      toast.error(exception.message);
    } finally {
      setBusy(false);
    }
  }

  const approved = (items ?? []).filter((item) => item.status === "approved");

  return (
    <div>
      <h1 className="mb-2 text-xl font-semibold">Справочник категорий</h1>
      <p className="mb-6 text-sm text-ink-soft">
        Категории служат и отраслями в профилях организаций. Значения не
        удаляются: дубль объединяется с существующим, все ссылки переносятся.
      </p>

      <form
        className="mb-6 flex flex-wrap gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          if (!name.trim()) return;
          run(
            () => api.post("/api/admin/dictionaries/categories", { name: name.trim() }),
            isAdmin ? "Значение добавлено" : "Значение предложено, ожидает утверждения",
          ).then(() => setName(""));
        }}
      >
        <input
          className="field max-w-sm flex-1"
          placeholder="Новое значение справочника"
          value={name}
          maxLength={100}
          onChange={(event) => setName(event.target.value)}
          aria-label="Новое значение справочника"
        />
        <button type="submit" className="btn-primary" disabled={busy}>
          {isAdmin ? "Добавить" : "Предложить"}
        </button>
      </form>

      {!items && <p className="text-sm text-ink-soft">Загружаем справочник…</p>}

      {items && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[42rem] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs text-ink-soft">
                <th className="py-2 pr-3 font-normal">Значение</th>
                <th className="py-2 pr-3 font-normal">Состояние</th>
                <th className="py-2 pr-3 font-normal">Используется</th>
                <th className="py-2 font-normal">Действия</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.category_id} className="border-b border-line/60 align-top">
                  <td className="py-2 pr-3">{item.name}</td>
                  <td className="py-2 pr-3">
                    <span className={`rounded px-2 py-0.5 text-xs ${STATUS_STYLES[item.status]}`}>
                      {item.status_name}
                    </span>
                  </td>
                  <td className="py-2 pr-3 text-xs text-ink-soft">
                    программ {item.usage_programs}, профилей {item.usage_profiles}
                  </td>
                  <td className="py-2">
                    {isAdmin && item.status === "proposed" && (
                      <button
                        type="button"
                        className="btn-secondary px-2 py-1 text-xs"
                        disabled={busy}
                        onClick={() =>
                          run(
                            () =>
                              api.post(
                                `/api/admin/dictionaries/categories/${item.category_id}/approve`,
                              ),
                            "Значение утверждено",
                          )
                        }
                      >
                        Утвердить
                      </button>
                    )}

                    {isAdmin && item.status !== "merged" && (
                      <div className="mt-1 flex flex-wrap items-center gap-1">
                        <select
                          className="field py-1 text-xs"
                          value={mergeInto[item.category_id] ?? ""}
                          onChange={(event) =>
                            setMergeInto({ ...mergeInto, [item.category_id]: event.target.value })
                          }
                          aria-label={`Объединить «${item.name}» со значением`}
                        >
                          <option value="">объединить со значением…</option>
                          {approved
                            .filter((target) => target.category_id !== item.category_id)
                            .map((target) => (
                              <option key={target.category_id} value={target.category_id}>
                                {target.name}
                              </option>
                            ))}
                        </select>
                        <button
                          type="button"
                          className="btn-secondary px-2 py-1 text-xs"
                          disabled={busy || !mergeInto[item.category_id]}
                          onClick={() =>
                            run(
                              () =>
                                api.post(
                                  `/api/admin/dictionaries/categories/${item.category_id}/merge`,
                                  { target_id: Number(mergeInto[item.category_id]) },
                                ),
                              "Значения объединены, ссылки перенесены",
                            )
                          }
                        >
                          Объединить
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
