import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import {
  bootstrapSession,
  clearTokens,
  login as apiLogin,
  registerUnauthorizedHandler,
} from "../api/client.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [status, setStatus] = useState("loading");
  const queryClient = useQueryClient();

  useEffect(() => {
    registerUnauthorizedHandler(() => {
      clearTokens();
      queryClient.clear();
      setStatus("anonymous");
    });
    bootstrapSession().then((alive) => setStatus(alive ? "authenticated" : "anonymous"));
  }, [queryClient]);

  const value = useMemo(
    () => ({
      status,
      isAuthenticated: status === "authenticated",
      async login(email, password) {
        await apiLogin(email, password);
        queryClient.clear();
        setStatus("authenticated");
      },
      logout() {
        clearTokens();
        queryClient.clear();
        setStatus("anonymous");
      },
    }),
    [status, queryClient],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
