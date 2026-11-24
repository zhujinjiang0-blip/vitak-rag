import type { ReactNode } from "react";
import type { AuthUser } from "./types";

export function AuthProvider({ children }: { children: ReactNode }) {
  return <>{children}</>;
}

export function useAuth(): {
  user: AuthUser | null;
  loading: boolean;
  signIn: (username: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  refresh: () => Promise<void>;
} {
  return {
    user: null,
    loading: false,
    async signIn() {
      throw new Error("Public demo does not support sign-in");
    },
    async signOut() {},
    async refresh() {}
  };
}
