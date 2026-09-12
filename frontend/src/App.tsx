import { Navigate, Route, Routes } from "react-router-dom";
import { getToken } from "./api/client";
import { Layout } from "./components/Layout";
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
