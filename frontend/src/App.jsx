import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { useAuth } from "./auth/AuthContext";
import Layout from "./components/Layout";
import Applications from "./pages/Applications";
import Catalog from "./pages/Catalog";
import ConfirmEmail from "./pages/ConfirmEmail";
import Login from "./pages/Login";
import ProgramList from "./pages/Matched";
import NotFound from "./pages/NotFound";
import Notifications from "./pages/Notifications";
import PasswordReset from "./pages/PasswordReset";
import ProgramDetail from "./pages/ProgramDetail";
import Profile from "./pages/Profile";
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
        <Route path="programs/:programId" element={<ProgramDetail />} />
        <Route path="archive" element={<Catalog archive />} />

        <Route path="login" element={<Login />} />
        <Route path="register" element={<Register />} />
        <Route path="confirm" element={<ConfirmEmail />} />
        <Route path="reset-password" element={<PasswordReset />} />

        <Route
          path="matched"
          element={
            <RequireAuth>
              <ProgramList mode="matched" />
            </RequireAuth>
          }
        />
        <Route
          path="favorites"
          element={
            <RequireAuth>
              <ProgramList mode="favorites" />
            </RequireAuth>
          }
        />
        <Route
          path="applications"
          element={
            <RequireAuth>
              <Applications />
            </RequireAuth>
          }
        />
        <Route
          path="notifications"
          element={
            <RequireAuth>
              <Notifications />
            </RequireAuth>
          }
        />
        <Route
          path="profile"
          element={
            <RequireAuth>
              <Profile />
            </RequireAuth>
          }
        />

        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
