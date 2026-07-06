import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext.jsx";
import { avatarColors, errorText, initials } from "../components/ui.jsx";

const DEMO_PASSWORD = "demo12345";
const DEMO_ACCOUNTS = [
  { email: "admin@demo.local", short: "Admin", capline: "admin · gestiona" },
  { email: "editor@demo.local", short: "Editor", capline: "ver·bajar·subir" },
  { email: "analyst@demo.local", short: "Analyst", capline: "ver·bajar" },
  { email: "provider@demo.local", short: "Provider", capline: "solo subir" },
];

export default function LoginPage() {
  const { status, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  if (status === "authenticated") {
    return <Navigate to={location.state?.from || "/files"} replace />;
  }

  const selected = DEMO_ACCOUNTS.find((account) => account.email === email);

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      navigate(location.state?.from || "/files", { replace: true });
    } catch (err) {
      setError(err);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-split">
      
      <div className="login-brand">
        <div className="brand-row">
          <div className="logo-box">D</div>
          <span className="brand-word">Drive Access Control</span>
        </div>
        <div>
          <h1 className="login-headline">
            Permisos por grupo
            <br />
            sobre una cuenta de Drive.
          </h1>
        </div>
        <div className="login-foot">Django + DRF · PostgreSQL · React · docker compose</div>
      </div>

      
      <div className="login-form-panel">
        <form className="login-card" onSubmit={handleSubmit}>
          <h2>Iniciar sesión</h2>
          <p className="lead">Accedé con tu cuenta corporativa.</p>

          <label htmlFor="login-email">Email</label>
          <input
            id="login-email"
            type="email"
            autoComplete="email"
            required
            autoFocus
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />

          <label htmlFor="login-password">Contraseña</label>
          <input
            id="login-password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          {error && (
            <p className="form-error" role="alert">
              {errorText(error)}
              {error.requestId && (
                <span className="mono"> · ref {error.requestId.slice(0, 12)}</span>
              )}
            </p>
          )}

          <button type="submit" className="btn-login" disabled={submitting}>
            {submitting
              ? "Ingresando…"
              : selected
                ? `Entrar como ${selected.short.toLowerCase()}`
                : "Entrar"}
          </button>

          <div className="login-divider">
            <span />
            <span className="label">Cuentas de demo</span>
            <span />
          </div>

          <div className="demo-grid">
            {DEMO_ACCOUNTS.map((account) => {
              const colors = avatarColors(account.email);
              return (
                <button
                  key={account.email}
                  type="button"
                  className={`demo-chip${email === account.email ? " selected" : ""}`}
                  onClick={() => {
                    setEmail(account.email);
                    setPassword(DEMO_PASSWORD);
                  }}
                >
                  <div className="demo-chip-head">
                    <div
                      className="avatar avatar-24"
                      style={{ background: colors.bg, color: colors.fg }}
                    >
                      {initials(account.email)}
                    </div>
                    <span className="demo-chip-name">{account.short}</span>
                  </div>
                  <div className="demo-chip-capline">{account.capline}</div>
                </button>
              );
            })}
          </div>
          <p className="login-hint">password de demo · {DEMO_PASSWORD}</p>
        </form>
      </div>
    </div>
  );
}
