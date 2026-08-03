import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { useAuth } from "./auth/AuthContext";
import Layout from "./components/Layout";
import Catalog from "./pages/Catalog";
import Login from "./pages/Login";
import NotFound from "./pages/NotFound";
import Register from "./pages/Register";

/**
 * Ограничение доступа к разделу. Скрытие раздела — удобство, а не защита:
 * запрос без прав отклонит сервер, даже если открыть адрес напрямую.
 */
function RequireAuth({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <p className="text-sm text-ink-soft">Загружаем…</p>;
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/programs" replace />} />
        <Route path="programs" element={<Catalog />} />
        <Route path="archive" element={<Catalog archive />} />

        <Route path="login" element={<Login />} />
        <Route path="register" element={<Register />} />

        <Route
          path="applications"
          element={
            <RequireAuth>
              <Placeholder title="Мои заявки" />
            </RequireAuth>
          }
        />
        <Route
          path="matched"
          element={
            <RequireAuth>
              <Placeholder title="Подходящие мне" />
            </RequireAuth>
          }
        />
        <Route
          path="profile"
          element={
            <RequireAuth>
              <Placeholder title="Профиль организации" />
            </RequireAuth>
          }
        />

        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}

/** Экран, который будет реализован следующим шагом. */
function Placeholder({ title }) {
  return (
    <div>
      <h1 className="mb-2 text-xl font-semibold">{title}</h1>
      <p className="text-sm text-ink-soft">Раздел в разработке.</p>
    </div>
  );
}
