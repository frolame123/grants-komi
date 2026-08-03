import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api } from "../api/client";
import { useToast } from "../components/Toast";

/**
 * Проверки повторяют серверные (FR-001) и срабатывают мгновенно, без запроса.
 * Это удобство, а не защита: те же правила проверяет сервер схемой Pydantic,
 * и обойти их через прямой запрос к API невозможно.
 */
function validate({ email, password, passwordConfirm, consent }) {
  const errors = {};

  if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) {
    errors.email = "Укажите адрес в формате имя@домен";
  }
  if (password.length < 8) {
    errors.password = "Пароль должен содержать не менее 8 символов";
  } else if (!/[a-zа-яё]/.test(password)) {
    errors.password = "Пароль должен содержать строчную букву";
  } else if (!/[A-ZА-ЯЁ]/.test(password)) {
    errors.password = "Пароль должен содержать прописную букву";
  } else if (!/\d/.test(password)) {
    errors.password = "Пароль должен содержать цифру";
  }
  if (password !== passwordConfirm) {
    errors.passwordConfirm = "Пароли не совпадают";
  }
  if (!consent) {
    errors.consent = "Без согласия на обработку персональных данных регистрация невозможна";
  }

  return errors;
}

export default function Register() {
  const toast = useToast();
  const navigate = useNavigate();

  const [form, setForm] = useState({
    email: "",
    password: "",
    passwordConfirm: "",
    consent: false,
  });
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined, form: undefined }));
  }

  async function submit(event) {
    event.preventDefault();
    const found = validate(form);
    setErrors(found);
    if (Object.keys(found).length) return;

    setBusy(true);
    try {
      await api.post("/api/auth/register", {
        email: form.email,
        password: form.password,
        password_confirm: form.passwordConfirm,
        pd_consent: form.consent,
      });
      toast.success("Письмо со ссылкой подтверждения отправлено на указанный адрес");
      navigate("/login", { replace: true });
    } catch (exception) {
      setErrors({ form: exception.message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-sm">
      <h1 className="mb-6 text-xl font-semibold">Регистрация</h1>

      <form onSubmit={submit} noValidate className="space-y-4">
        <Field
          id="email"
          label="Адрес электронной почты"
          type="email"
          autoComplete="username"
          value={form.email}
          error={errors.email}
          onChange={(value) => update("email", value)}
        />

        <Field
          id="password"
          label="Пароль"
          type="password"
          autoComplete="new-password"
          value={form.password}
          error={errors.password}
          hint="Не менее 8 символов, буквы обоих регистров и хотя бы одна цифра"
          onChange={(value) => update("password", value)}
        />

        <Field
          id="passwordConfirm"
          label="Повторите пароль"
          type="password"
          autoComplete="new-password"
          value={form.passwordConfirm}
          error={errors.passwordConfirm}
          onChange={(value) => update("passwordConfirm", value)}
        />

        <div>
          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              className="mt-0.5"
              checked={form.consent}
              onChange={(event) => update("consent", event.target.checked)}
              aria-invalid={Boolean(errors.consent)}
            />
            <span>
              Согласен на обработку персональных данных в соответствии с Федеральным
              законом № 152-ФЗ
            </span>
          </label>
          {errors.consent && (
            <p className="mt-1 text-xs text-alert" role="alert">
              {errors.consent}
            </p>
          )}
        </div>

        {errors.form && (
          <p role="alert" className="rounded border border-alert/40 bg-alert/5 px-3 py-2 text-sm text-alert">
            {errors.form}
          </p>
        )}

        <button type="submit" className="btn-primary w-full" disabled={busy}>
          {busy ? "Отправляем…" : "Зарегистрироваться"}
        </button>
      </form>

      <p className="mt-4 text-sm text-ink-soft">
        Уже зарегистрированы?{" "}
        <Link to="/login" className="hover:text-ink hover:underline">
          Войти
        </Link>
      </p>
    </div>
  );
}

function Field({ id, label, error, hint, onChange, ...props }) {
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm">
        {label}
      </label>
      <input
        id={id}
        className={`field ${error ? "field-error" : ""}`}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined}
        onChange={(event) => onChange(event.target.value)}
        {...props}
      />
      {error ? (
        <p id={`${id}-error`} className="mt-1 text-xs text-alert" role="alert">
          {error}
        </p>
      ) : (
        hint && (
          <p id={`${id}-hint`} className="mt-1 text-xs text-ink-soft">
            {hint}
          </p>
        )
      )}
    </div>
  );
}
