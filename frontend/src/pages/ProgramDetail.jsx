/**
 * Карточка программы: полные сведения, избранное и создание заявки.
 *
 * Ссылка на первоисточник обязательна в каждой карточке: сведения собраны из
 * открытых источников, и пользователь должен иметь возможность проверить их
 * там, где они опубликованы (ГК РФ ч. 4, п. 4.1.6 ТЗ).
 */

import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { formatAmount, formatDate } from "../components/ProgramCard";
import { useToast } from "../components/Toast";

const APPLICANT_NAMES = {
  IP: "Индивидуальные предприниматели",
  OOO: "Общества с ограниченной ответственностью",
  NKO: "Некоммерческие организации",
  SMZ: "Самозанятые",
};

const EXTRA_NAMES = {
  co_financing: "Софинансирование",
  reporting: "Отчётность",
  min_employees: "Минимальная численность сотрудников",
  age_limit: "Возрастное ограничение",
  project_duration_months: "Длительность проекта, месяцев",
  stages: "Этапы приёма",
};

export default function ProgramDetail() {
  const { programId } = useParams();
  const { user } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();

  const [program, setProgram] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .get(`/api/programs/${programId}`)
      .then(setProgram)
      .catch((exception) => setError(exception.message));
  }, [programId]);

  async function addToFavorites() {
    setBusy(true);
    try {
      await api.post(`/api/favorites/${programId}`);
      toast.success("Программа добавлена в избранное");
    } catch (exception) {
      toast.error(exception.message);
    } finally {
      setBusy(false);
    }
  }

  async function createApplication() {
    setBusy(true);
    try {
      const application = await api.post("/api/applications", {
        program_id: Number(programId),
      });
      toast.success("Заявка создана в статусе черновика");
      navigate(`/applications#${application.application_id}`);
    } catch (exception) {
      toast.error(exception.message);
    } finally {
      setBusy(false);
    }
  }

  if (error) {
    return (
      <div className="py-12 text-center">
        <h1 className="mb-2 text-xl font-semibold">Программа не найдена</h1>
        <p className="mb-6 text-sm text-ink-soft">{error}</p>
        <Link to="/programs" className="btn-secondary">
          Вернуться в каталог
        </Link>
      </div>
    );
  }

  if (!program) return <p className="text-sm text-ink-soft">Загружаем карточку…</p>;

  const archived = program.status === "ARCH";
  const extra = Object.entries(program.extra_json ?? {});

  return (
    <article className="mx-auto max-w-3xl">
      {archived && (
        <p className="mb-4 rounded border border-line bg-surface px-3 py-2 text-sm">
          Приём заявок по этой программе завершён. Карточка сохранена для истории.
        </p>
      )}

      <p className="mb-2 text-xs text-ink-soft">
        {program.category ?? "Категория не указана"}
      </p>
      <h1 className="mb-2 text-2xl font-semibold">{program.title}</h1>
      <p className="mb-6 text-ink-soft">{program.organizer}</p>

      <dl className="mb-6 grid gap-x-6 gap-y-3 border-y border-line py-4 sm:grid-cols-2">
        <Row label="Сумма">{formatAmount(program.amount)}</Row>
        <Row label="Приём заявок до">
          {formatDate(program.deadline)}
          {program.days_left !== null && program.days_left >= 0 && (
            <span className={program.days_left <= 7 ? " text-warning" : " text-ink-soft"}>
              {" "}
              (осталось {program.days_left})
            </span>
          )}
        </Row>
        <Row label="Кто может подать">
          {program.applicant_types.length
            ? program.applicant_types.map((type) => APPLICANT_NAMES[type] ?? type).join(", ")
            : "уточняется"}
        </Row>
        <Row label="Регионы действия">
          {program.regions.length ? program.regions.join(", ") : "уточняется"}
        </Row>
        <Row label="Источник сведений">{program.source}</Row>
      </dl>

      {extra.length > 0 && (
        <section className="mb-6">
          <h2 className="mb-2 text-base font-medium">Дополнительные условия</h2>
          <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
            {extra.map(([key, value]) => (
              <Row key={key} label={EXTRA_NAMES[key] ?? key}>
                {Array.isArray(value) ? value.join(", ") : String(value)}
              </Row>
            ))}
          </dl>
        </section>
      )}

      <div className="flex flex-wrap gap-2">
        <a
          className="btn-secondary"
          href={program.source_url}
          target="_blank"
          rel="noopener noreferrer"
        >
          Открыть первоисточник
        </a>

        {user && !archived && (
          <>
            <button type="button" className="btn-secondary" onClick={addToFavorites} disabled={busy}>
              В избранное
            </button>
            <button type="button" className="btn-primary" onClick={createApplication} disabled={busy}>
              Подать заявку
            </button>
          </>
        )}

        {!user && !archived && (
          <Link to="/login" className="btn-primary">
            Войдите, чтобы вести заявку
          </Link>
        )}
      </div>

      <p className="mt-6 text-xs text-ink-soft">
        Заявка подаётся на площадке организатора. Система хранит статус, который
        вы отмечаете самостоятельно, и напоминает о сроках.
      </p>
    </article>
  );
}

function Row({ label, children }) {
  return (
    <div>
      <dt className="text-xs text-ink-soft">{label}</dt>
      <dd className="text-sm">{children}</dd>
    </div>
  );
}
