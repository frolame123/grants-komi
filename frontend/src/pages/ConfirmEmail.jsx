/**
 * Подтверждение адреса по ссылке из письма (FR-002).
 *
 * Сервер при первом переходе выдаёт пару токенов — пользователь сразу
 * оказывается в системе. При повторном переходе токенов нет, и страница
 * предлагает войти: адрес уже подтверждён, второй раз подтверждать нечего.
 */

import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toast";

export default function ConfirmEmail() {
  const [params] = useSearchParams();
  const { acceptTokens } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();

  const [state, setState] = useState({ status: "pending", message: "" });
  // Строгий режим React вызывает эффекты дважды: без защиты токен был бы
  // потрачен первым вызовом, а второй показал бы «ссылка недействительна»
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;

    const token = params.get("token");
    if (!token) {
      setState({ status: "error", message: "В ссылке нет токена подтверждения" });
      return;
    }

    api
      .get(`/api/auth/confirm?token=${encodeURIComponent(token)}`)
      .then(async (result) => {
        if (result.access_token) {
          await acceptTokens(result);
          toast.success("Адрес подтверждён, вы вошли в систему");
          navigate("/profile", { replace: true });
          return;
        }
        setState({ status: "done", message: result.detail });
      })
      .catch((exception) => setState({ status: "error", message: exception.message }));
  }, [params, acceptTokens, navigate, toast]);

  return (
    <div className="mx-auto max-w-md py-12 text-center">
      {state.status === "pending" && <p className="text-sm text-ink-soft">Проверяем ссылку…</p>}

      {state.status !== "pending" && (
        <>
          <h1 className="mb-2 text-xl font-semibold">
            {state.status === "done" ? "Адрес подтверждён" : "Ссылка не сработала"}
          </h1>
          <p className="mb-6 text-sm text-ink-soft">{state.message}</p>
          <Link to="/login" className="btn-primary">
            Перейти ко входу
          </Link>
        </>
      )}
    </div>
  );
}
