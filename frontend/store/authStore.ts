import { create } from "zustand";

type AuthState = {
  accessToken: string | null;
  email: string | null;
  setAccessToken: (accessToken: string | null) => void;
  setSession: (session: { accessToken: string | null; email?: string | null }) => void;
};

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  email: null,
  setAccessToken: (accessToken) => set({ accessToken, email: null }),
  setSession: ({ accessToken, email = null }) => set({ accessToken, email })
}));
