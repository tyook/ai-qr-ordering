import { create } from "zustand";
import { customerLogin, customerRegister, customerGoogleAuth, customerAppleAuth } from "@/lib/api";

const TOKEN_KEY = "customer_access_token";
const REFRESH_KEY = "customer_refresh_token";

interface CustomerAuthState {
  isAuthenticated: boolean;
  customer: { id: string; email: string; name: string } | null;

  login: (email: string, password: string) => Promise<void>;
  register: (data: {
    email: string;
    password: string;
    name: string;
    phone?: string;
    link_order_id?: string;
  }) => Promise<void>;
  googleLogin: (token: string, linkOrderId?: string) => Promise<void>;
  appleLogin: (token: string, name?: string, linkOrderId?: string) => Promise<void>;
  logout: () => void;
  checkAuth: () => boolean;
}

export const useCustomerAuthStore = create<CustomerAuthState>((set) => ({
  isAuthenticated:
    typeof window !== "undefined" && !!localStorage.getItem(TOKEN_KEY),
  customer: null,

  login: async (email, password) => {
    const data = await customerLogin(email, password);
    localStorage.setItem(TOKEN_KEY, data.access);
    localStorage.setItem(REFRESH_KEY, data.refresh);
    set({ isAuthenticated: true, customer: data.customer });
  },

  register: async (formData) => {
    const data = await customerRegister(formData);
    localStorage.setItem(TOKEN_KEY, data.access);
    localStorage.setItem(REFRESH_KEY, data.refresh);
    set({ isAuthenticated: true, customer: data.customer });
  },

  googleLogin: async (token, linkOrderId) => {
    const data = await customerGoogleAuth(token, linkOrderId);
    localStorage.setItem(TOKEN_KEY, data.access);
    localStorage.setItem(REFRESH_KEY, data.refresh);
    set({ isAuthenticated: true, customer: data.customer });
  },

  appleLogin: async (token, name, linkOrderId) => {
    const data = await customerAppleAuth(token, name, linkOrderId);
    localStorage.setItem(TOKEN_KEY, data.access);
    localStorage.setItem(REFRESH_KEY, data.refresh);
    set({ isAuthenticated: true, customer: data.customer });
  },

  logout: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
    set({ isAuthenticated: false, customer: null });
  },

  checkAuth: () => {
    return !!localStorage.getItem(TOKEN_KEY);
  },
}));
