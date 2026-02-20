import { createContext, useContext, type ReactNode } from "react";
import type { CurrentUser } from "../services/auth";

const AuthContext = createContext<CurrentUser | null>(null);

export function AuthProvider({ children, user }: { children: ReactNode; user: CurrentUser | null }) {
  return <AuthContext.Provider value={user}>{children}</AuthContext.Provider>;
}

export function useAuth(): CurrentUser | null {
  return useContext(AuthContext);
}
