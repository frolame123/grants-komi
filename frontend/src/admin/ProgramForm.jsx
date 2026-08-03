/**
 * Создание и правка карточки программы (FR-007).
 *
 * Тот же экран обслуживает оба случая: ручное заведение карточки для
 * источников, не поддающихся разбору, и дозаполнение того, что принёс
 * парсер. Публикация невозможна без категории и срока подачи — это
 * ограничение базы, и форма предупреждает о нём заранее.
 */

import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { api } from "../api/client";
import { useToast } from "../components/Toast";

const APPLICANT_TYPES = [
  ["IP", "Индивидуальные предприниматели"],
  ["OOO", "Общества с ограниченной ответственностью"],
  ["NKO", "Некоммерческие организации"],
  ["SMZ", "Самозанятые"],
];

const EMPTY = {
  source_id: "",
  category_id: "",
  title: "",
  organizer: "",
  amount: "",
  deadline: "",
  source_url: "",
  applicant_types: [],
  regions: ["Республика Коми"],
};

export default function ProgramForm() {
  const { programId } = useParams();
  const toast = useToast();
  const navigate = useNavigate();

  const [form, setForm] = useState(EMPTY);
  const [program, setProgram] = useState(null);
  const [sources, setSources] = useState([]);
  const [categories, setCategories] = useState([]);
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/api/categories").then(setCategories).catch(() => setCategories([]));
    api
      .get("/api/admin/stats")
      .then((stats) =>
        setSources(stats.sources.map((s) => ({ source_id: s.source_id, name: s.source_name }))),
      )
      .catch(() => setSources([]));
  }, []);

  // Карточка читается маршрутом панели: публичный отдаёт только
  // опубликованные и архивные, а дозаполнять нужно именно черновик
  useEffect(() => {
    if (!programId) return;
    api.get(`/api/admin/programs/${programId}`).then((loaded) => {
      setProgram(loaded);
      setForm({
        source_id: String(loaded.source_id),
        category_id: loaded.category_id ?? "",
        title: loaded.title,
        organizer: loaded.organizer,
        amount: loaded.amount ?? "",
        deadline: loaded.deadline ?? "",
        source_url: loaded.source_url,
        applicant_types: loaded.applicant_types,
        regions: loaded.regions.length ? loaded.regions : ["Республика Коми"],
      });
    });
  }, [programId]);

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined, form: undefined }));
  }

  function toggleType(value) {
    setForm((current) => ({
      ...current,
      applicant_types: current.applicant_types.includes(value)
        ? current.applicant_types.filter((item) => item !== value)
        : [...current.applicant_types, value],
    }));
  }

  function validate() {
    const found = {};
    if (!form.source_id) found.source_id = "Выберите источник";
    if (form.title.trim().length < 5) found.title = "Наименование не короче 5 символов";
    if (form.organizer.trim().length < 2) found.organizer = "Укажите организатора";
    if (!/^https?:\/\//.test(form.source_url)) found.source_url = "Ссылка должна начинаться с http";
    if (form.amount !== "" && Number(form.amount) <= 0) found.amount = "Сумма должна быть больше нуля";
    return found;
  }

  async function submit(event) {
    event.preventDefault();
    const found = validate();
    setErrors(found);
    if (Object.keys(found).length) return;

    const payload = {
      source_id: Number(form.source_id),
      category_id: form.category_id ? Number(form.category_id) : null,
      title: form.title.trim(),
      organizer: form.organizer.trim(),
      amount: form.amount === "" ? null : Number(form.amount),
      deadline: form.deadline || null,
      source_url: form.source_url.trim(),
      applicant_types: form.applicant_types,
      regions: form.regions.filter(Boolean),
      extra_json: {},
    };

    setBusy(true);
    try {
      if (programId) {
        await api.put(`/api/admin/programs/${programId}`, payload);
        toast.success("Карточка сохранена");
      } else {
        const created = await api.post("/api/admin/programs", payload);
        toast.success("Карточка создана черновиком");
        navigate(`/admin/programs/${created.program_id}`, { replace: true });
      }
    } catch (exception) {
      setErrors({ form: exception.message });
      toast.error("Не удалось сохранить карточку");
    } finally {
      setBusy(false);
    }
  }

  async function archive() {
    setBusy(true);
    try {
      await api.post(`/api/admin/programs/${programId}/archive`);
      toast.success("Карточка снята с публикации");
      navigate("/admin/moderation");
    } catch (exception) {
      toast.error(exception.message);
    } finally {
      setBusy(false);
    }
  }

  const publishable = form.category_id && form.deadline;

  return (
    <div className="max-w-2xl">
      <h1 className="mb-2 text-xl font-semibold">
        {programId ? "Карточка программы" : "Создание карточки"}
      </h1>
      <p className="mb-6 text-sm text-ink-soft">
        {programId
          ? "Правка применяется сразу, без очереди. Изменение фиксируется в журнале аудита с перечнем полей."
          : "Карточка создаётся черновиком. Опубликовать её можно после заполнения категории и срока подачи."}
      </p>

      {programId && !publishable && (
        <p className="mb-4 rounded border border-warning/40 bg-warning/5 px-3 py-2 text-sm text-warning">
          Публикация невозможна: не заполнены{" "}
          {[!form.category_id && "категория", !form.deadline && "срок подачи"]
            .filter(Boolean)
            .join(" и ")}
          .
        </p>
      )}

      <form onSubmit={submit} noValidate className="grid gap-4 sm:grid-cols-2">
        <Select
          label="Источник"
          value={form.source_id}
          error={errors.source_id}
          onChange={(value) => update("source_id", value)}
          options={[["", "Выберите источник"], ...sources.map((s) => [s.source_id, s.name])]}
        />

        <Select
          label="Категория"
          value={form.category_id}
          onChange={(value) => update("category_id", value)}
          options={[
            ["", "Не выбрана"],
            ...categories.map((c) => [c.category_id, c.name]),
          ]}
        />

        <Text
          label="Наименование"
          className="sm:col-span-2"
          value={form.title}
          error={errors.title}
          maxLength={300}
          onChange={(value) => update("title", value)}
        />

        <Text
          label="Организатор"
          value={form.organizer}
          error={errors.organizer}
          maxLength={200}
          onChange={(value) => update("organizer", value)}
        />

        <Text
          label="Сумма, ₽"
          type="number"
          min="0"
          step="1000"
          value={form.amount}
          error={errors.amount}
          onChange={(value) => update("amount", value)}
        />

        <Text
          label="Приём заявок до"
          type="date"
          value={form.deadline}
          onChange={(value) => update("deadline", value)}
        />

        <Text
          label="Ссылка на первоисточник"
          className="sm:col-span-2"
          value={form.source_url}
          error={errors.source_url}
          maxLength={500}
          onChange={(value) => update("source_url", value)}
        />

        <fieldset className="sm:col-span-2">
          <legend className="mb-1 text-sm">Кто может подать</legend>
          <div className="flex flex-wrap gap-3">
            {APPLICANT_TYPES.map(([value, title]) => (
              <label key={value} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.applicant_types.includes(value)}
                  onChange={() => toggleType(value)}
                />
                {title}
              </label>
            ))}
          </div>
        </fieldset>

        <Text
          label="Регионы действия, через запятую"
          className="sm:col-span-2"
          value={form.regions.join(", ")}
          onChange={(value) => update("regions", value.split(",").map((item) => item.trim()))}
        />

        {errors.form && (
          <p
            role="alert"
            className="rounded border border-alert/40 bg-alert/5 px-3 py-2 text-sm text-alert sm:col-span-2"
          >
            {errors.form}
          </p>
        )}

        <div className="flex flex-wrap gap-2 sm:col-span-2">
          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? "Сохраняем…" : programId ? "Сохранить" : "Создать карточку"}
          </button>
          {programId && program?.status !== "ARCH" && (
            <button type="button" className="btn-secondary" onClick={archive} disabled={busy}>
              Снять с публикации
            </button>
          )}
        </div>
      </form>
    </div>
  );
}

function Text({ label, className = "", error, onChange, ...props }) {
  return (
    <label className={className}>
      <span className="mb-1 block text-sm">{label}</span>
      <input
        className={`field ${error ? "field-error" : ""}`}
        aria-invalid={Boolean(error)}
        onChange={(event) => onChange(event.target.value)}
        {...props}
      />
      {error && (
        <span className="mt-1 block text-xs text-alert" role="alert">
          {error}
        </span>
      )}
    </label>
  );
}

function Select({ label, value, error, onChange, options }) {
  return (
    <label>
      <span className="mb-1 block text-sm">{label}</span>
      <select
        className={`field ${error ? "field-error" : ""}`}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map(([optionValue, title]) => (
          <option key={optionValue} value={optionValue}>
            {title}
          </option>
        ))}
      </select>
      {error && (
        <span className="mt-1 block text-xs text-alert" role="alert">
          {error}
        </span>
      )}
    </label>
  );
}
