import { Navigate, useLocation } from "react-router-dom";

import { Spinner, ErrorState } from "../components/ui.jsx";
import { useAuth } from "./AuthContext.jsx";
import { useMe } from "./useMe.js";


export function RequireAuth({ children }) {
  const { status } = useAuth();
  const location = useLocation();

  if (status === "loading") return <Spinner label="Restaurando sesión…" />;
  if (status === "anonymous") {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return children;
}

export function RequireAdmin({ children }) {
  const me = useMe();

  if (me.isPending) return <Spinner label="Cargando perfil…" />;
  if (me.isError) return <ErrorState error={me.error} />;
  if (me.data.role !== "admin") return <Navigate to="/files" replace />;
  return children;
}
