import { Navigate, Route, Routes } from "react-router-dom";

import { RequireAdmin, RequireAuth } from "./auth/guards.jsx";
import Layout from "./components/Layout.jsx";
import AdminPage from "./pages/AdminPage.jsx";
import FilesPage from "./pages/FilesPage.jsx";
import LoginPage from "./pages/LoginPage.jsx";

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
        <Route path="/files" element={<FilesPage />} />
        <Route
          path="/admin"
          element={
            <RequireAdmin>
              <AdminPage />
            </RequireAdmin>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/files" replace />} />
    </Routes>
  );
}
