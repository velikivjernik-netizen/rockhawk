import { useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { api, getToken, User } from "./api/client";
import { Layout } from "./components/Layout";
import { AdminPage } from "./pages/AdminPage";
import { AuditPage } from "./pages/AuditPage";
import { HotPage } from "./pages/HotPage";
import { LoginPage } from "./pages/LoginPage";
import { MatterHomePage } from "./pages/MatterHomePage";
import { MattersPage } from "./pages/MattersPage";
import { TablePage } from "./pages/TablePage";

function RequireAuth({ children }: { children: JSX.Element }) {
  if (!getToken()) return <Navigate to="/login" replace />;
  return children;
}

function RequireAdmin({ children }: { children: JSX.Element }) {
  const [allowed, setAllowed] = useState<boolean | null>(null);
  useEffect(() => {
    api<User>("/api/auth/me")
      .then((user) => setAllowed(user.role === "admin"))
      .catch(() => setAllowed(false));
  }, []);
  if (allowed === null) return <p>Checking administrator access…</p>;
  if (!allowed) return <Navigate to="/matters" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route
          path="/admin"
          element={
            <RequireAdmin>
              <AdminPage />
            </RequireAdmin>
          }
        />
        <Route path="/matters" element={<MattersPage />} />
        <Route path="/matters/:matterId" element={<MatterHomePage />} />
        <Route path="/matters/:matterId/tables/:tableId" element={<TablePage />} />
        <Route path="/matters/:matterId/hot" element={<HotPage />} />
        <Route path="/matters/:matterId/audit" element={<AuditPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/matters" replace />} />
    </Routes>
  );
}
