/**
 * Персональный подбор (FR-005) и избранное — списки программ без фильтров.
 *
 * Подбор недоступен, пока не заполнены тип организации и отрасль: сервер
 * отвечает кодом 412, и экран объясняет, что делать, вместо показа ошибки.
 */

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, withQuery } from "../api/client";
import ProgramCard from "../components/ProgramCard";

export default function ProgramList({ mode }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [needsProfile, setNeedsProfile] = useState(false);
  const [page, setPage] = useState(1);

  const matched = mode === "matched";
  const path = matched ? "/api/programs/matched" : "/api/favorites";

  useEffect(() => {
    setError(null);
    setNeedsProfile(false);
    api
      .get(withQuery(path, { page }))
      .then(setData)
      .catch((exception) => {
        if (exception.status === 412) setNeedsProfile(true);
        else setError(exception.message);
      });
  }, [path, page]);

  if (needsProfile) {
    return (
      <div className="mx-auto max-w-lg rounded border border-line p-8 text-center">
        <h1 className="mb-2 text-xl font-semibold">Подбор недоступен</h1>
        <p className="mb-6 text-sm text-ink-soft">
          Чтобы система подобрала программы, заполните в профиле тип организации
          и отрасль. Остальные поля влияют на точность, но не обязательны.
        </p>
        <Link to="/profile" className="btn-primary">
          Заполнить профиль
        </Link>
      </div>
    );
  }

  const pages = data ? Math.ceil(data.total / data.page_size) : 0;

  return (
    <div>
      <h1 className="mb-2 text-xl font-semibold">
        {matched ? "Подходящие вашей организации" : "Избранное"}
      </h1>
      <p className="mb-6 text-sm text-ink-soft">
        {matched
          ? "Программы отобраны по типу организации и сроку подачи, затем упорядочены по степени соответствия профилю."
          : "Программы, которые вы отметили. По ним приходят напоминания о сроках."}
      </p>

      {error && (
        <p role="alert" className="rounded border border-alert/40 bg-alert/5 px-3 py-2 text-sm text-alert">
          {error}
        </p>
      )}

      {data && data.items.length === 0 && (
        <div className="rounded border border-line p-8 text-center">
          <p className="mb-3 text-sm">
            {matched
              ? "Подходящих программ не найдено. Попробуйте уточнить отрасль или цель финансирования в профиле."
              : "Список пуст. Отмечайте программы в каталоге, чтобы не пропустить сроки."}
          </p>
          <Link to="/programs" className="btn-secondary">
            Перейти в каталог
          </Link>
        </div>
      )}

      {data && data.items.length > 0 && (
        <>
          <p className="mb-4 text-sm text-ink-soft">Всего: {data.total}</p>
          <ul className="grid gap-4 md:grid-cols-2">
            {data.items.map((program) => (
              <li key={program.program_id}>
                <ProgramCard program={program} />
              </li>
            ))}
          </ul>

          {pages > 1 && (
            <nav className="mt-6 flex items-center justify-center gap-2" aria-label="Страницы">
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
