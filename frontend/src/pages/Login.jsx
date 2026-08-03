import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toast";

export default function Login() {
  const { login } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const location = useLocation();

  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(form.email, form.password);
      toast.success("Вход выполнен");
      navigate(location.state?.from ?? "/programs", { replace: true });
    } catch (exception) {
      setError(exception.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-sm">
      <h1 className="mb-6 text-xl font-semibold">Вход</h1>

      <form onSubmit={submit} noValidate className="space-y-4">
        <div>
          <label htmlFor="email" className="mb-1 block text-sm">
            Адрес электронной почты
          </label>
          <input
            id="email"
            type="email"
            autoComplete="username"
            required
            className="field"
            value={form.email}
            onChange={(event) => setForm({ ...form, email: event.target.value })}
          />
        </div>

        <div>
          <label htmlFor="password" className="mb-1 block text-sm">
            Пароль
          </label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            className="field"
            value={form.password}
            onChange={(event) => setForm({ ...form, password: event.target.value })}
          />
        </div>

        {error && (
          <p role="alert" className="rounded border border-alert/40 bg-alert/5 px-3 py-2 text-sm text-alert">
            {error}
          </p>
        )}

        <button type="submit" className="btn-primary w-full" disabled={busy}>
          {busy ? "Проверяем…" : "Войти"}
        </button>
      </form>

      <div className="mt-4 flex justify-between text-sm text-ink-soft">
        <Link to="/register" className="hover:text-ink hover:underline">
          Зарегистрироваться
        </Link>
        <Link to="/password-reset" className="hover:text-ink hover:underline">
          Забыли пароль?
        </Link>
      </div>
    </div>
  );
}
