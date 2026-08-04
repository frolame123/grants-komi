/**
 * Профиль организации (FR-003).
 *
 * Контрольное число ИНН проверяется на клиенте тем же алгоритмом ФНС, что и
 * на сервере: опечатка видна сразу, до отправки формы. Серверная проверка при
 * этом остаётся — она и есть защита, клиентская лишь избавляет от лишнего
 * запроса.
 */

import { useEffect, useState } from "react";

import { api } from "../api/client";
import { useToast } from "../components/Toast";
import { validateInn } from "../lib/inn";

const ORG_TYPES = [
  ["IP", "Индивидуальный предприниматель"],
  ["OOO", "Общество с ограниченной ответственностью"],
  ["NKO", "Некоммерческая организация"],
  ["SMZ", "Самозанятый"],
];

const SIZES = [
  ["", "Не указан"],
  ["micro", "Микропредприятие"],
  ["small", "Малое предприятие"],
  ["medium", "Среднее предприятие"],
];

const EMPTY = {
  org_type: "OOO",
  inn: "",
  category_id: "",
  city: "",
  street: "",
  house: "",
  org_size: "",
  goal: "",
  region: "Республика Коми",
};

export default function Profile() {
  const toast = useToast();
  const [form, setForm] = useState(EMPTY);
  const [categories, setCategories] = useState([]);
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([
      api.get("/api/categories").catch(() => []),
      api.get("/api/profile").catch((exception) => {
        if (exception.status === 404) return null; // профиль ещё не заполнен
        throw exception;
      }),
    ])
      .then(([list, profile]) => {
        setCategories(list);
        if (profile) {
          setForm({
            ...EMPTY,
            ...profile,
            category_id: profile.category_id ?? "",
            street: profile.street ?? "",
            house: profile.house ?? "",
            org_size: profile.org_size ?? "",
            goal: profile.goal ?? "",
          });
        }
      })
      .finally(() => setLoading(false));
  }, []);

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined, form: undefined }));
  }

  function validate() {
    const found = {};
    const innError = validateInn(form.inn, form.org_type);
    if (innError) found.inn = innError;
    if (!form.category_id) found.category_id = "Выберите отрасль";
    if (form.city.trim().length < 2) found.city = "Укажите город";
    return found;
  }

  async function submit(event) {
    event.preventDefault();
    const found = validate();
    setErrors(found);
    if (Object.keys(found).length) return;

    setBusy(true);
    try {
      await api.put("/api/profile", {
        ...form,
        category_id: Number(form.category_id),
        org_size: form.org_size || null,
        street: form.street || null,
        house: form.house || null,
        goal: form.goal || null,
      });
      toast.success("Профиль организации сохранён");
    } catch (exception) {
      setErrors({ form: exception.message });
      toast.error("Не удалось сохранить профиль");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <p className="text-sm text-ink-soft">Загружаем профиль…</p>;

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-2 text-xl font-semibold">Профиль организации</h1>
      <p className="mb-6 text-sm text-ink-soft">
        Тип организации и отрасль обязательны: без них недоступен персональный
        подбор программ.
      </p>

      <form onSubmit={submit} noValidate className="grid gap-4 sm:grid-cols-2">
        <label className="sm:col-span-1">
          <span className="mb-1 block text-sm">Тип организации</span>
          <select
            className="field"
            value={form.org_type}
            onChange={(event) => update("org_type", event.target.value)}
          >
            {ORG_TYPES.map(([value, title]) => (
              <option key={value} value={value}>
                {title}
              </option>
            ))}
          </select>
        </label>

        <TextField
          label="ИНН"
          value={form.inn}
          error={errors.inn}
          hint={form.org_type === "OOO" ? "10 цифр" : "12 цифр"}
          inputMode="numeric"
          maxLength={12}
          onChange={(value) => update("inn", value.replace(/\D/g, ""))}
        />

        <label className="sm:col-span-2">
          <span className="mb-1 block text-sm">Отрасль</span>
          <select
            className={`field ${errors.category_id ? "field-error" : ""}`}
            value={form.category_id}
            onChange={(event) => update("category_id", event.target.value)}
            aria-invalid={Boolean(errors.category_id)}
          >
            <option value="">Выберите отрасль</option>
            {categories.map((category) => (
              <option key={category.category_id} value={category.category_id}>
                {category.name}
              </option>
            ))}
          </select>
          {errors.category_id && (
            <p className="mt-1 text-xs text-alert" role="alert">
              {errors.category_id}
            </p>
          )}
        </label>

        <TextField
          label="Город"
          value={form.city}
          error={errors.city}
          onChange={(value) => update("city", value)}
        />

        <label>
          <span className="mb-1 block text-sm">Размер организации</span>
          <select
            className="field"
            value={form.org_size}
            onChange={(event) => update("org_size", event.target.value)}
          >
            {SIZES.map(([value, title]) => (
              <option key={value} value={value}>
                {title}
              </option>
            ))}
          </select>
        </label>

        <TextField
          label="Улица"
          value={form.street}
          onChange={(value) => update("street", value)}
        />
        <TextField
          label="Дом"
          value={form.house}
          onChange={(value) => update("house", value)}
        />

        <label className="sm:col-span-2">
          <span className="mb-1 block text-sm">Цель финансирования</span>
          <textarea
            className="field min-h-20"
            maxLength={300}
            value={form.goal}
            onChange={(event) => update("goal", event.target.value)}
            placeholder="Например: закупка оборудования для мастерской"
          />
          <span className="mt-1 block text-xs text-ink-soft">
            Учитывается при подборе: совпадение слов с назначением программы даёт
            дополнительные баллы
          </span>
        </label>

        {errors.form && (
          <p
            role="alert"
            className="rounded border border-alert/40 bg-alert/5 px-3 py-2 text-sm text-alert sm:col-span-2"
          >
            {errors.form}
          </p>
        )}

        <div className="sm:col-span-2">
          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? "Сохраняем…" : "Сохранить профиль"}
          </button>
        </div>
      </form>
    </div>
  );
}

function TextField({ label, value, error, hint, onChange, ...props }) {
  return (
    <label>
      <span className="mb-1 block text-sm">{label}</span>
      <input
        className={`field ${error ? "field-error" : ""}`}
        value={value}
        aria-invalid={Boolean(error)}
        onChange={(event) => onChange(event.target.value)}
        {...props}
      />
      {error ? (
        <span className="mt-1 block text-xs text-alert" role="alert">
          {error}
        </span>
      ) : (
        hint && <span className="mt-1 block text-xs text-ink-soft">{hint}</span>
      )}
    </label>
  );
}
