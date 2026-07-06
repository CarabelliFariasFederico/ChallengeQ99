import { useQuery } from "@tanstack/react-query";

import { fetchMe } from "../api/endpoints.js";
import { useAuth } from "./AuthContext.jsx";

export function useMe() {
  const { isAuthenticated } = useAuth();
  return useQuery({
    queryKey: ["me"],
    queryFn: fetchMe,
    enabled: isAuthenticated,
    staleTime: 30_000,
  });
}
