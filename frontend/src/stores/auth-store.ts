import { create } from "zustand";
import { apiFetch } from "@/lib/api";

interface AuthState {
  isAuthenticated: boolean;
  user: { id: string; email: string; first_name: string; last_name: string } | null;
  login: (email: string, password: string) => Promise<void>;
  register: (data: {
    email: string;
    password: string;
    first_name: string;
    last_name: string;
  }) => Promise<void>;
  logout: () => void;
  checkAuth: () => boolean;
}

export const useAuthStore = create<AuthState>((set) => ({
  isAuthenticated:
    typeof window !== "undefined" && !!localStorage.getItem("access_token"),
  user: null,

  login: async (email, password) => {
    const data = await apiFetch<{ access: string; refresh: string }>(
      "/api/auth/login/",
      {
        method: "POST",
        body: JSON.stringify({ email, password }),
      }
    );
    localStorage.setItem("access_token", data.access);
    localStorage.setItem("refresh_token", data.refresh);
    set({ isAuthenticated: true });
  },

  register: async (formData) => {
    const data = await apiFetch<{
      access: string;
      refresh: string;
      user: { id: string; email: string; first_name: string; last_name: string };
    }>("/api/auth/register/", {
      method: "POST",
      body: JSON.stringify(formData),
    });
    localStorage.setItem("access_token", data.access);
    localStorage.setItem("refresh_token", data.refresh);
    set({ isAuthenticated: true, user: data.user });
  },

  logout: () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    set({ isAuthenticated: false, user: null });
  },

  checkAuth: () => {
    return !!localStorage.getItem("access_token");
  },
}));
