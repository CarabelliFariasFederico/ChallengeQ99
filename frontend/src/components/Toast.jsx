import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";

import { errorText } from "./ui.jsx";


const ToastContext = createContext(null);

let nextId = 1;

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const timers = useRef({});

  const dismiss = useCallback((id) => {
    setToasts((current) => current.filter((t) => t.id !== id));
    clearTimeout(timers.current[id]);
    delete timers.current[id];
  }, []);

  const push = useCallback(
    (toast) => {
      const id = nextId++;
      setToasts((current) => [...current, { id, ...toast }]);
      timers.current[id] = setTimeout(() => dismiss(id), 3400);
    },
    [dismiss],
  );

  const value = useMemo(
    () => ({
      success: (message, tag = "OK") => push({ type: "success", tag, message }),
      info: (message, tag = "info") => push({ type: "info", tag, message }),
      error: (err, tag) =>
        push({
          type: "error",
          tag: tag ?? errorTag(err),
          message: errorText(err),
          requestId: err?.requestId,
        }),
    }),
    [push],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toasts" aria-live="polite">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast toast-${toast.type}`} role="status">
            <div className="toast-head">
              <span className="toast-tag">{toast.tag}</span>
              {toast.requestId && <span className="toast-rid">{toast.requestId.slice(0, 12)}</span>}
              <button
                type="button"
                className="toast-close"
                aria-label="Cerrar aviso"
                onClick={() => dismiss(toast.id)}
                style={toast.requestId ? {} : { marginLeft: "auto" }}
              >
                ×
              </button>
            </div>
            <div className="toast-msg">{toast.message}</div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function errorTag(err) {
  const status = err?.status ? String(err.status) : "";
  const code = err?.code && err.code !== "unknown" ? err.code : "error";
  return `${status} ${code}`.trim();
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside <ToastProvider>");
  return ctx;
}
