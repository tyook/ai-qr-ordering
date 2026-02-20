const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5005";

let isRefreshing = false;
let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken =
    typeof window !== "undefined" ? localStorage.getItem("refresh_token") : null;
  if (!refreshToken) return null;

  try {
    const response = await fetch(`${API_URL}/api/auth/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh: refreshToken }),
    });

    if (!response.ok) return null;

    const data = await response.json();
    localStorage.setItem("access_token", data.access);
    return data.access;
  } catch {
    return null;
  }
}

async function clearAuth() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  const { useAuthStore } = await import("@/stores/auth-store");
  useAuthStore.getState().logout();
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  _isRetry = false
): Promise<T> {
  const url = `${API_URL}${path}`;
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  const token =
    typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  if (token) {
    (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(url, { ...options, headers });

  if (response.status === 401 && !_isRetry && typeof window !== "undefined") {
    // Deduplicate concurrent refresh attempts
    if (!isRefreshing) {
      isRefreshing = true;
      refreshPromise = refreshAccessToken().finally(() => {
        isRefreshing = false;
        refreshPromise = null;
      });
    }

    const newToken = await refreshPromise;

    if (newToken) {
      // Retry the original request with the new token
      return apiFetch<T>(path, options, true);
    }

    // Refresh failed — clear everything
    await clearAuth();
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Session expired. Please log in again.");
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `API error: ${response.status}`);
  }

  return response.json();
}

import type {
  PublicMenu,
  ParsedOrderResponse,
  ConfirmOrderItem,
  OrderResponse,
  CreatePaymentResponse,
  CustomerAuthResponse,
  CustomerProfile,
  CustomerOrderHistoryItem,
  SavedPaymentMethod,
  Subscription,
} from "@/types";

export async function fetchMenu(slug: string): Promise<PublicMenu> {
  return apiFetch<PublicMenu>(`/api/order/${slug}/menu/`);
}

export async function parseOrder(
  slug: string,
  rawInput: string
): Promise<ParsedOrderResponse> {
  return apiFetch<ParsedOrderResponse>(`/api/order/${slug}/parse/`, {
    method: "POST",
    body: JSON.stringify({ raw_input: rawInput }),
  });
}

export async function confirmOrder(
  slug: string,
  items: ConfirmOrderItem[],
  rawInput: string,
  tableIdentifier: string,
  language: string,
  customerName?: string,
  customerPhone?: string
): Promise<OrderResponse> {
  return apiFetch<OrderResponse>(`/api/order/${slug}/confirm/`, {
    method: "POST",
    body: JSON.stringify({
      items,
      raw_input: rawInput,
      table_identifier: tableIdentifier,
      language,
      customer_name: customerName || "",
      customer_phone: customerPhone || "",
    }),
  });
}

export async function createPayment(
  slug: string,
  items: ConfirmOrderItem[],
  rawInput: string,
  tableIdentifier: string,
  language: string,
  customerName?: string,
  customerPhone?: string,
  paymentMethodId?: string,
  saveCard?: boolean,
): Promise<CreatePaymentResponse> {
  return customerApiFetch<CreatePaymentResponse>(`/api/order/${slug}/create-payment/`, {
    method: "POST",
    body: JSON.stringify({
      items,
      raw_input: rawInput,
      table_identifier: tableIdentifier,
      language,
      customer_name: customerName || "",
      customer_phone: customerPhone || "",
      payment_method_id: paymentMethodId || "",
      save_card: saveCard || false,
      return_url: window.location.href,
    }),
  });
}

export async function fetchOrderStatus(
  slug: string,
  orderId: string
): Promise<OrderResponse> {
  return apiFetch<OrderResponse>(`/api/order/${slug}/status/${orderId}/`);
}

export async function saveCardConsent(
  slug: string,
  orderId: string,
): Promise<void> {
  await apiFetch(`/api/order/${slug}/save-card/${orderId}/`, {
    method: "PATCH",
  });
}

const CUSTOMER_TOKEN_KEY = "customer_access_token";
const CUSTOMER_REFRESH_KEY = "customer_refresh_token";

export async function customerApiFetch<T>(
  path: string,
  options: RequestInit = {},
  _isRetry = false
): Promise<T> {
  const url = `${API_URL}${path}`;
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  const token = typeof window !== "undefined"
    ? localStorage.getItem(CUSTOMER_TOKEN_KEY)
    : null;
  if (token) {
    (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(url, { ...options, headers });

  if (response.status === 401 && !_isRetry && typeof window !== "undefined") {
    // Try refresh
    const refreshToken = localStorage.getItem(CUSTOMER_REFRESH_KEY);
    if (refreshToken) {
      try {
        const refreshResp = await fetch(`${API_URL}/api/customer/auth/refresh/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh: refreshToken }),
        });
        if (refreshResp.ok) {
          const data = await refreshResp.json();
          localStorage.setItem(CUSTOMER_TOKEN_KEY, data.access);
          // Retry
          return customerApiFetch<T>(path, options, true);
        }
      } catch {}
    }
    // Clear auth
    localStorage.removeItem(CUSTOMER_TOKEN_KEY);
    localStorage.removeItem(CUSTOMER_REFRESH_KEY);
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || error.email?.[0] || `API error: ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

export async function customerRegister(data: {
  email: string;
  password: string;
  name: string;
  phone?: string;
  link_order_id?: string;
}): Promise<CustomerAuthResponse> {
  return customerApiFetch<CustomerAuthResponse>("/api/customer/auth/register/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function customerLogin(
  email: string,
  password: string,
): Promise<CustomerAuthResponse> {
  return customerApiFetch<CustomerAuthResponse>("/api/customer/auth/login/", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function fetchCustomerProfile(): Promise<CustomerProfile> {
  return customerApiFetch<CustomerProfile>("/api/customer/profile/");
}

export async function updateCustomerProfile(
  data: Partial<CustomerProfile>,
): Promise<CustomerProfile> {
  return customerApiFetch<CustomerProfile>("/api/customer/profile/", {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function fetchCustomerOrders(): Promise<CustomerOrderHistoryItem[]> {
  return customerApiFetch<CustomerOrderHistoryItem[]>("/api/customer/orders/");
}

export async function customerGoogleAuth(
  token: string,
  linkOrderId?: string,
): Promise<CustomerAuthResponse> {
  const response = await fetch(`${API_URL}/api/customer/auth/google/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, link_order_id: linkOrderId }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `API error: ${response.status}`);
  }
  return response.json();
}

export async function customerAppleAuth(
  token: string,
  name?: string,
  linkOrderId?: string,
): Promise<CustomerAuthResponse> {
  const response = await fetch(`${API_URL}/api/customer/auth/apple/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, name, link_order_id: linkOrderId }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `API error: ${response.status}`);
  }
  return response.json();
}

export async function fetchPaymentMethods(): Promise<SavedPaymentMethod[]> {
  return customerApiFetch<SavedPaymentMethod[]>("/api/customer/payment-methods/");
}

export async function deletePaymentMethod(pmId: string): Promise<void> {
  await customerApiFetch<void>(`/api/customer/payment-methods/${pmId}/`, {
    method: "DELETE",
  });
}

// Subscription API
export async function fetchSubscription(slug: string): Promise<Subscription> {
  return apiFetch<Subscription>(`/api/restaurants/${slug}/subscription/`);
}

export async function createCheckoutSession(
  slug: string,
  plan: string,
  interval: "monthly" | "annual"
): Promise<{ checkout_url: string }> {
  return apiFetch<{ checkout_url: string }>(
    `/api/restaurants/${slug}/subscription/checkout/`,
    {
      method: "POST",
      body: JSON.stringify({ plan, interval }),
    }
  );
}

export async function createBillingPortal(
  slug: string
): Promise<{ portal_url: string }> {
  return apiFetch<{ portal_url: string }>(
    `/api/restaurants/${slug}/subscription/portal/`,
    { method: "POST" }
  );
}

export async function cancelSubscription(slug: string): Promise<Subscription> {
  return apiFetch<Subscription>(
    `/api/restaurants/${slug}/subscription/cancel/`,
    { method: "POST" }
  );
}

export async function reactivateSubscription(slug: string): Promise<Subscription> {
  return apiFetch<Subscription>(
    `/api/restaurants/${slug}/subscription/reactivate/`,
    { method: "POST" }
  );
}

