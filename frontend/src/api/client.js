/**
 * Обращения к REST API.
 *
 * Токен доступа живёт тридцать минут и хранится в памяти вкладки: при
 * перезагрузке страницы он теряется и восстанавливается обменом токена
 * обновления. Токен обновления лежит в хранилище браузера — иначе вход не
 * переживал бы перезагрузку.
 *
 * Обмен выполняется прозрачно: если сервер ответил 401, запрос повторяется
 * один раз после получения новой пары. Пользователь этого не замечает.
 */

const REFRESH_KEY = "grants_refresh_token";

let accessToken = null;
let refreshing = null;
let onUnauthorized = () => {};

export function setAccessToken(token) {
  accessToken = token;
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_KEY);
}

export function saveTokens({ access_token, refresh_token }) {
  accessToken = access_token;
  localStorage.setItem(REFRESH_KEY, refresh_token);
}

export function clearTokens() {
  accessToken = null;
  localStorage.removeItem(REFRESH_KEY);
}

export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler;
}

export class ApiError extends Error {
  constructor(message, status, payload) {
    super(message);
    this.status = status;
    this.payload = payload;
  }
}

/** Читаемое сообщение из ответа сервера. */
function messageFrom(payload, status) {
  if (!payload) return `Ошибка ${status}`;
  const detail = payload.detail;
  if (typeof detail === "string") return detail;
  // Ошибки проверки схемы приходят списком: показываем первую
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0];
    return first.msg?.replace(/^Value error, /, "") ?? `Ошибка ${status}`;
  }
  return `Ошибка ${status}`;
}

async function refreshTokens() {
  const token = getRefreshToken();
  if (!token) return false;

  // Параллельные запросы, получившие 401, ждут один общий обмен, а не
  // устраивают гонку из нескольких обновлений подряд
  refreshing ??= fetch("/api/auth/refresh", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: token }),
  })
    .then(async (response) => {
      if (!response.ok) return false;
      saveTokens(await response.json());
      return true;
    })
    .catch(() => false)
    .finally(() => {
      refreshing = null;
    });

  return refreshing;
}

async function send(path, { method = "GET", body, retry = true } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;

  let response;
  try {
    response = await fetch(path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    // Тайм-аут и обрыв соединения: текст сообщения задан п. 4.2.0 ТЗ
    throw new ApiError("Не удалось связаться с сервером, повторите попытку", 0, null);
  }

  if (response.status === 401 && retry && getRefreshToken()) {
    if (await refreshTokens()) {
      return send(path, { method, body, retry: false });
    }
    clearTokens();
    onUnauthorized();
  }

  if (response.status === 204) return null;

  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(messageFrom(payload, response.status), response.status, payload);
  }
  return payload;
}

/** Путь с параметрами запроса; пустые значения не передаются. */
export function withQuery(path, params = {}) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.append(key, value);
    }
  }
  const query = search.toString();
  return query ? `${path}?${query}` : path;
}

export const api = {
  get: (path) => send(path),
  post: (path, body) => send(path, { method: "POST", body }),
  put: (path, body) => send(path, { method: "PUT", body }),
  patch: (path, body) => send(path, { method: "PATCH", body }),
  delete: (path) => send(path, { method: "DELETE" }),
};
