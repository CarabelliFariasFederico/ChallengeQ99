
export function Spinner({ label = "Cargando…" }) {
  return (
    <p className="state-loading" role="status" aria-busy="true">
      {label}
    </p>
  );
}

export function EmptyState({ title, children }) {
  return (
    <div className="state-empty">
      <p className="state-title">{title}</p>
      {children}
    </div>
  );
}

export function ErrorState({ error }) {
  return (
    <div className="state-error" role="alert">
      <div>{errorText(error)}</div>
      {error?.requestId && <div className="request-id">ref: {error.requestId}</div>}
    </div>
  );
}


export function errorText(error) {
  if (!error) return "Algo salió mal.";
  const detail = firstDetail(error.details);
  if (detail && detail !== error.message) return `${error.message} ${detail}`;
  return error.message || "Algo salió mal.";
}

function firstDetail(details) {
  if (!details) return null;
  if (typeof details === "string") return details;
  if (Array.isArray(details)) return String(details[0]);
  if (typeof details === "object") {
    const first = Object.values(details)[0];
    return first ? String(Array.isArray(first) ? first[0] : first) : null;
  }
  return null;
}

export function formatBytes(size) {
  if (size === null || size === undefined) return "—";
  if (size < 1024) return `${size} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = size;
  let unit = -1;
  do {
    value /= 1024;
    unit += 1;
  } while (value >= 1024 && unit < units.length - 1);
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[unit]}`;
}


const DEMO_AVATARS = {
  "admin@demo.local": { bg: "#22467a", fg: "#fff" },
  "editor@demo.local": { bg: "#edf5ee", fg: "#2f6b3f" },
  "analyst@demo.local": { bg: "#eef2f8", fg: "#22467a" },
  "provider@demo.local": { bg: "#faf1e5", fg: "#a6531a" },
};

export function avatarColors(email) {
  return DEMO_AVATARS[email] ?? { bg: "#eef2f8", fg: "#22467a" };
}

export function initials(email) {
  if (!email) return "·";
  const parts = email.split("@")[0].split(/[^a-zA-Z0-9]+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return (parts[0] || email).slice(0, 2).toUpperCase();
}

export function localPart(email) {
  return email ? email.split("@")[0] : "";
}
