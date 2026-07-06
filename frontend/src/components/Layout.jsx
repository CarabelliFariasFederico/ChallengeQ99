import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext.jsx";
import { useMe } from "../auth/useMe.js";
import { avatarColors, initials } from "./ui.jsx";

export default function Layout() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const me = useMe();
  const data = me.data;
  const active = data?.active_credential;

  const pageTitle = location.pathname.startsWith("/admin") ? "Administración" : "Archivos";
  const avatar = avatarColors(data?.email);

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="side-logo">
          <div className="logo-box">D</div>
          <span className="grotesk side-brand">Access Control</span>
        </div>

        <nav className="side-nav" aria-label="Principal">
          <NavLink
            to="/files"
            className={({ isActive }) => `side-item${isActive ? " active" : ""}`}
          >
            <span className="icon">▤</span> Archivos
          </NavLink>
          
          {data?.role === "admin" && (
            <NavLink
              to="/admin"
              className={({ isActive }) => `side-item${isActive ? " active" : ""}`}
            >
              <span className="icon">⚙</span> Administración
            </NavLink>
          )}
        </nav>

        <div className="side-user">
          <div className="avatar avatar-32" style={{ background: avatar.bg, color: avatar.fg }}>
            {initials(data?.email)}
          </div>
          <div className="side-user-info">
            <div className="side-user-name">{data?.email}</div>
            <div className="mono side-user-role">
              {data?.role === "admin" ? "Administrador" : "Miembro"}
            </div>
          </div>
          <button
            type="button"
            className="side-logout"
            title="Salir"
            aria-label="Cerrar sesión"
            onClick={() => {
              logout();
              navigate("/login");
            }}
          >
            ⏻
          </button>
        </div>
      </aside>

      <main className="main">
        <div className="topbar">
          <div className="grotesk page-title">{pageTitle}</div>
          <div className="topbar-right">
            <div className="cred-pill">
              <span
                className="cred-dot"
                style={{ background: active?.present ? "#2f6b3f" : "#b3ab9c" }}
              />
              <span className="cred-pill-label">Cuenta activa:</span>
              <span className="mono cred-pill-value">
                {active?.present ? active.account_label : "ninguna"}
              </span>
            </div>
            {data?.drive_gateway && (
              <span className="mono gw-badge">gateway: {data.drive_gateway}</span>
            )}
          </div>
        </div>
        <Outlet />
      </main>
    </div>
  );
}
