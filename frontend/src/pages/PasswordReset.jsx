/**
 * Восстановление пароля (FR-009).
 *
 * Один адрес обслуживает оба шага: без токена в ссылке показывается запрос
 * письма, с токеном — форма нового пароля. Ответ на запрос письма всегда
 * одинаков и не раскрывает, зарегистрирован ли адрес.
 */

import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { api } from "../api/client";
import { useToast } from "../components/Toast";

function validatePassword(password) {
  if (password.length < 8) return "Пароль должен содержать не менее 8 символов";
  if (!/[a-zа-яё]/.test(password)) return "Пароль должен содержать строчную букву";
  if (!/[A-ZА-ЯЁ]/.test(password)) return "Пароль должен содержать прописную букву";
  if (!/\d/.test(password)) return "Пароль должен содержать цифру";
  return null;
}

export default function PasswordReset() {
  const [params] = useSearchParams();
  const token = params.get("token");

  return token ? <SetNewPassword token={token} /> : <RequestLink />;
}

function RequestLink() {
  const toast = useToast();
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    try {
      const result = await api.post("/api/auth/password/forgot", { email });
      setSent(true);
      toast.success(result.detail);
    } catch (exception) {
      toast.error(exception.message);
    } finally {
      setBusy(false);
    }
  }

  if (sent) {
    return (
      <div className="mx-auto max-w-md py-12 text-center">
        <h1 className="mb-2 text-xl font-semibold">Проверьте почту</h1>
        <p className="mb-6 text-sm text-ink-soft">
          Если аккаунт существует, письмо отправлено. Ссылка действует один час.
        </p>
        <Link to="/login" className="btn-secondary">
          Вернуться ко входу
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-sm">
      <h1 className="mb-2 text-xl font-semibold">Восстановление пароля</h1>
      <p className="mb-6 text-sm text-ink-soft">
        Укажите адрес, на который зарегистрирована учётная запись. Пришлём ссылку
        для смены пароля.
      </p>

      <form onSubmit={submit} noValidate className="space-y-4">
        <label>
          <span className="mb-1 block text-sm">Адрес электронной почты</span>
          <input
            type="email"
            required
            className="field"
            autoComplete="username"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </label>
        <button type="submit" className="btn-primary w-full" disabled={busy}>
          {busy ? "Отправляем…" : "Отправить ссылку"}
        </button>
      </form>
    </div>
  );
}

function SetNewPassword({ token }) {
  const toast = useToast();
  const navigate = useNavigate();

  const [form, setForm] = useState({ password: "", confirm: "" });
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();

    const found = {};
    const passwordError = validatePassword(form.password);
    if (passwordError) found.password = passwordError;
    if (form.password !== form.confirm) found.confirm = "Пароли не совпадают";
    setErrors(found);
    if (Object.keys(found).length) return;

    setBusy(true);
    try {
      await api.post("/api/auth/password/reset", {
        token,
        password: form.password,
        password_confirm: form.confirm,
      });
      toast.success("Пароль изменён, войдите с новым паролем");
      navigate("/login", { replace: true });
    } catch (exception) {
      setErrors({ form: exception.message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-sm">
      <h1 className="mb-6 text-xl font-semibold">Новый пароль</h1>

      <form onSubmit={submit} noValidate className="space-y-4">
        <label>
          <span className="mb-1 block text-sm">Новый пароль</span>
          <input
            type="password"
            autoComplete="new-password"
            className={`field ${errors.password ? "field-error" : ""}`}
            value={form.password}
            onChange={(event) => setForm({ ...form, password: event.target.value })}
          />
          {errors.password ? (
            <span className="mt-1 block text-xs text-alert" role="alert">
              {errors.password}
            </span>
          ) : (
            <span className="mt-1 block text-xs text-ink-soft">
              Не менее 8 символов, буквы обоих регистров и хотя бы одна цифра
            </span>
          )}
        </label>

        <label>
          <span className="mb-1 block text-sm">Повторите пароль</span>
          <input
            type="password"
            autoComplete="new-password"
            className={`field ${errors.confirm ? "field-error" : ""}`}
            value={form.confirm}
            onChange={(event) => setForm({ ...form, confirm: event.target.value })}
          />
          {errors.confirm && (
            <span className="mt-1 block text-xs text-alert" role="alert">
              {errors.confirm}
            </span>
          )}
        </label>

        {errors.form && (
          <p role="alert" className="rounded border border-alert/40 bg-alert/5 px-3 py-2 text-sm text-alert">
            {errors.form}
          </p>
        )}

        <button type="submit" className="btn-primary w-full" disabled={busy}>
          {busy ? "Сохраняем…" : "Сменить пароль"}
        </button>
      </form>
    </div>
  );
}
