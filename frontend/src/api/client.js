
export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const REFRESH_KEY = "drive-permissions.refresh";

let accessToken = null;
let onUnauthorized = () => {};
let refreshInFlight = null;

export class ApiError extends Error {
  constructor(envelope, status) {
    super(envelope?.message || `Request failed (HTTP ${status || "network"})`);
    this.code = envelope?.code ?? "unknown";
    this.details = envelope?.details ?? null;
    this.requestId = envelope?.request_id ?? null;
    this.status = status;
  }
}

export function registerUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

export function getAccessToken() {
  return accessToken;
}

function storeTokens({ access, refresh }) {
  if (access) accessToken = access;
  if (refresh) sessionStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens() {
  accessToken = null;
  sessionStorage.removeItem(REFRESH_KEY);
}

async function envelopeError(res) {
  let body = null;
  try {
    body = await res.json();
  } catch {}
  return new ApiError(body, res.status);
}

export async function login(email, password) {
  const res = await fetch(`${API_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw await envelopeError(res);
  storeTokens(await res.json());
}

function refreshSession() {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      const refresh = sessionStorage.getItem(REFRESH_KEY);
      if (!refresh) return false;
      const res = await fetch(`${API_URL}/api/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh }),
      });
      if (!res.ok) return false;
      storeTokens(await res.json());
      return true;
    })().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}


export function bootstrapSession() {
  return refreshSession();
}


export async function ensureFreshAccess() {
  if (!accessToken) await refreshSession();
  return accessToken;
}

export async function apiFetch(path, options = {}, retry = true) {
  const headers = { ...(options.headers || {}) };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (res.status === 401 && retry) {
    if (await refreshSession()) return apiFetch(path, options, false);
    clearTokens();
    onUnauthorized();
    throw await envelopeError(res);
  }
  if (!res.ok) throw await envelopeError(res);
  return res;
}

export async function apiJson(path, options = {}) {
  const res = await apiFetch(path, options);
  return res.status === 204 ? null : res.json();
}

export async function getHealth() {
  const res = await fetch(`${API_URL}/healthz`);
  if (!res.ok) throw new Error(`healthz responded ${res.status}`);
  return res.json();
}
