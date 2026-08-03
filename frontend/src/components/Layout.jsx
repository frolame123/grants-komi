/**
 * Общий каркас страниц: шапка с меню, хлебные крошки, подвал.
 *
 * Меню собирается по роли: заявителю не показываются разделы модерации, но
 * это удобство, а не защита — доступ ограничивает сервер.
 */

import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";

const TITLES = {
  programs: "Каталог программ",
  archive: "Завершённые конкурсы",
  matched: "Подходящие мне",
  favorites: "Избранное",
  applications: "Мои заявки",
  profile: "Профиль организации",
  notifications: "Уведомления",
  admin: "Панель управления",
  moderation: "Модерация",
  users: "Пользователи",
  dictionaries: "Справочники",
  audit: "Журнал аудита",
  sources: "Источники",
  stats: "Статистика",
  login: "Вход",
  register: "Регистрация",
};

function Breadcrumbs() {
  const { pathname } = useLocation();
  const parts = pathname.split("/").filter(Boolean);

  if (!parts.length) return null;

  return (
    <nav aria-label="Хлебные крошки" className="border-b border-line bg-surface">
      <ol className="mx-auto flex max-w-6xl flex-wrap gap-1 px-4 py-2 text-xs text-ink-soft">
        <li>
          <Link to="/" className="hover:text-ink hover:underline">
            Главная
          </Link>
        </li>
        {parts.map((part, index) => {
          const path = "/" + parts.slice(0, index + 1).join("/");
          const label = TITLES[part] ?? decodeURIComponent(part);
          const last = index === parts.length - 1;
          return (
            <li key={path} className="flex gap-1">
              <span aria-hidden="true">/</span>
              {last ? (
                <span className="text-ink" aria-current="page">
                  {label}
                </span>
              ) : (
                <Link to={path} className="hover:text-ink hover:underline">
                  {label}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

function MenuLink({ to, children }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `rounded px-3 py-2 text-sm transition-colors ${
          isActive ? "bg-ink text-white" : "text-ink-soft hover:bg-surface hover:text-ink"
        }`
      }
    >
      {children}
    </NavLink>
  );
}

export default function Layout() {
  const { user, isStaff, logout } = useAuth();
  const { pathname } = useLocation();
  const [unread, setUnread] = useState(0);

  // Счётчик непрочитанных обновляется при смене раздела: отдельный опрос по
  // таймеру ради значка не нужен, а после прочтения число должно измениться
  useEffect(() => {
    if (!user) {
      setUnread(0);
      return;
    }
    api
      .get("/api/notifications?page=1")
      .then((data) => setUnread(data.unread))
      .catch(() => setUnread(0));
  }, [user, pathname]);

  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:m-2 focus:rounded focus:bg-ink focus:px-3 focus:py-2 focus:text-white"
      >
        Перейти к содержанию
      </a>

      <header className="border-b border-line">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
          <Link to="/" className="mr-auto text-base font-semibold tracking-tight">
            Гранты Коми
          </Link>

          <nav className="flex flex-wrap items-center gap-1" aria-label="Основное меню">
            <MenuLink to="/programs">Каталог</MenuLink>
            {user && <MenuLink to="/matched">Подходящие мне</MenuLink>}
            {user && <MenuLink to="/favorites">Избранное</MenuLink>}
            {user && <MenuLink to="/applications">Мои заявки</MenuLink>}
            {user && (
              <MenuLink to="/notifications">
                Уведомления
                {unread > 0 && (
                  <span
                    className="ml-1 rounded-full bg-alert px-1.5 py-0.5 text-[10px] font-medium text-white"
                    aria-label={`непрочитанных: ${unread}`}
                  >
                    {unread}
                  </span>
                )}
              </MenuLink>
            )}
            {isStaff && <MenuLink to="/admin">Управление</MenuLink>}
          </nav>

          <div className="flex items-center gap-2">
            {user ? (
              <>
                <Link
                  to="/profile"
                  className="max-w-[12rem] truncate text-sm text-ink-soft hover:text-ink hover:underline"
                  title={user.email}
                >
                  {user.email}
                </Link>
                <button type="button" onClick={logout} className="btn-secondary">
                  Выйти
                </button>
              </>
            ) : (
              <>
                <Link to="/login" className="btn-secondary">
                  Войти
                </Link>
                <Link to="/register" className="btn-primary">
                  Регистрация
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      <Breadcrumbs />

      <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
        <Outlet />
      </main>

      <footer className="border-t border-line bg-surface">
        <div className="mx-auto flex max-w-6xl flex-wrap gap-x-6 gap-y-1 px-4 py-4 text-xs text-ink-soft">
          <span>
            Информационная система мер грантовой поддержки МСП и НКО Республики Коми
          </span>
          <span className="ml-auto">
            Сведения собраны из открытых источников, первоисточник указан в каждой карточке
          </span>
        </div>
      </footer>
    </div>
  );
}
