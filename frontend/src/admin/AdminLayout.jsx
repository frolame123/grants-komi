/**
 * Панель управления: боковое меню и рабочая область.
 *
 * Разделы показываются по роли. Контент-менеджер видит модерацию,
 * справочники и карточки программ; администратор — дополнительно
 * пользователей, журнал аудита, прогоны агрегации и сводку.
 */

import { NavLink, Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

const SECTIONS = [
  { to: "/admin", label: "Сводка", end: true, admin: true },
  { to: "/admin/moderation", label: "Очередь модерации" },
  { to: "/admin/programs/new", label: "Создать карточку" },
  { to: "/admin/dictionaries", label: "Справочники" },
  { to: "/admin/users", label: "Пользователи", admin: true },
  { to: "/admin/sources", label: "Прогоны агрегации", admin: true },
  { to: "/admin/audit", label: "Журнал аудита", admin: true },
];

export default function AdminLayout() {
  const { user, loading, isStaff, isAdmin } = useAuth();
  const location = useLocation();

  if (loading) return <p className="text-sm text-ink-soft">Загружаем…</p>;
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  if (!isStaff) {
    return (
      <div className="mx-auto max-w-lg py-12 text-center">
        <h1 className="mb-2 text-xl font-semibold">Раздел недоступен</h1>
        <p className="text-sm text-ink-soft">
          Панель управления доступна контент-менеджерам и администраторам.
        </p>
      </div>
    );
  }

  const visible = SECTIONS.filter((section) => !section.admin || isAdmin);

  return (
    <div className="grid gap-6 lg:grid-cols-[15rem_1fr]">
      <nav aria-label="Разделы панели управления" className="lg:border-r lg:border-line lg:pr-4">
        <ul className="flex flex-wrap gap-1 lg:flex-col">
          {visible.map((section) => (
            <li key={section.to}>
              <NavLink
                to={section.to}
                end={section.end}
                className={({ isActive }) =>
                  `block rounded px-3 py-2 text-sm transition-colors ${
                    isActive ? "bg-ink text-white" : "text-ink-soft hover:bg-surface hover:text-ink"
                  }`
                }
              >
                {section.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      <div className="min-w-0">
        <Outlet />
      </div>
    </div>
  );
}
