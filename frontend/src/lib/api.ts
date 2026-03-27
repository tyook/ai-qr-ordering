const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5005";

function getCookie(name: string): string {
  if (typeof document === "undefined") return "";
  const match = document.cookie.match(new RegExp(`(^| )${name}=([^;]+)`));
  return match ? match[2] : "";
}

let isRefreshing = false;
let refreshPromise: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  try {
    const resp = await fetch(`${API_URL}/api/auth/refresh/`, {
      method: "POST",
      credentials: "include",
    });
    return resp.ok;
  } catch {
    return false;
  }
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  _isRetry = false
): Promise<T> {
  const url = `${API_URL}${path}`;
  const method = (options.method || "GET").toUpperCase();
  const headers: Record<string, string> = {
    ...(!(options.body instanceof FormData) && { "Content-Type": "application/json" }),
    ...(options.headers as Record<string, string>),
  };

  if (method !== "GET" && method !== "HEAD") {
    const csrfToken = getCookie("csrftoken");
    if (csrfToken) {
      headers["X-CSRFToken"] = csrfToken;
    }
  }

  const response = await fetch(url, {
    ...options,
    headers,
    credentials: "include",
  });

  if (response.status === 401 && !_isRetry) {
    if (!isRefreshing) {
      isRefreshing = true;
      refreshPromise = tryRefresh().finally(() => {
        isRefreshing = false;
        refreshPromise = null;
      });
    }

    const refreshed = await refreshPromise;
    if (refreshed) {
      return apiFetch<T>(path, options, true);
    }

    const { useAuthStore } = await import("@/stores/auth-store");
    useAuthStore.getState().clearAuth();
    throw new Error("Session expired. Please log in again.");
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(
      error.detail || error.email?.[0] || `API error: ${response.status}`
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

import type {
  PublicMenu,
  ParsedOrderResponse,
  ConfirmOrderItem,
  OrderResponse,
  CreatePaymentResponse,
  AuthResponse,
  User,
  OrderHistoryItem,
  OrderDetail,
  SavedPaymentMethod,
  Subscription,
  POSConnectionResponse,
  POSSyncLog,
  MenuVersion,
  ParsedMenu,
} from "@/types";

// ── Auth ──
export async function register(data: {
  email: string;
  password: string;
  first_name?: string;
  last_name?: string;
  name?: string;
  phone?: string;
  link_order_id?: string;
}): Promise<AuthResponse> {
  return apiFetch<AuthResponse>("/api/auth/register/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function login(
  email: string,
  password: string
): Promise<AuthResponse> {
  return apiFetch<AuthResponse>("/api/auth/login/", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function googleAuth(
  token: string,
  linkOrderId?: string
): Promise<AuthResponse> {
  return apiFetch<AuthResponse>("/api/auth/google/", {
    method: "POST",
    body: JSON.stringify({ token, link_order_id: linkOrderId }),
  });
}

export async function appleAuth(
  token: string,
  name?: string,
  linkOrderId?: string
): Promise<AuthResponse> {
  return apiFetch<AuthResponse>("/api/auth/apple/", {
    method: "POST",
    body: JSON.stringify({ token, name, link_order_id: linkOrderId }),
  });
}

export async function logout(): Promise<void> {
  await apiFetch("/api/auth/logout/", { method: "POST" });
}

export async function fetchMe(): Promise<User> {
  return apiFetch<User>("/api/auth/me/");
}

export async function updateProfile(data: Partial<User>): Promise<User> {
  return apiFetch<User>("/api/auth/me/", {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function fetchCsrfToken(): Promise<void> {
  await apiFetch("/api/auth/csrf/");
}

// ── Account ──
export async function fetchOrderHistory(): Promise<OrderHistoryItem[]> {
  return apiFetch<OrderHistoryItem[]>("/api/account/orders/");
}

export async function fetchOrderDetail(orderId: string): Promise<OrderDetail> {
  return apiFetch<OrderDetail>(`/api/account/orders/${orderId}/`);
}

export async function fetchPaymentMethods(): Promise<SavedPaymentMethod[]> {
  return apiFetch<SavedPaymentMethod[]>("/api/account/payment-methods/");
}

export async function deletePaymentMethod(pmId: string): Promise<void> {
  await apiFetch<void>(`/api/account/payment-methods/${pmId}/`, {
    method: "DELETE",
  });
}

// ── Public Order Flow ──
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
  allergies?: string[]
): Promise<CreatePaymentResponse> {
  return apiFetch<CreatePaymentResponse>(
    `/api/order/${slug}/create-payment/`,
    {
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
        return_url: typeof window !== "undefined" ? window.location.href : "",
        allergies: allergies || [],
      }),
    }
  );
}

export async function fetchOrderStatus(
  slug: string,
  orderId: string
): Promise<OrderResponse> {
  return apiFetch<OrderResponse>(`/api/order/${slug}/status/${orderId}/`);
}

export async function confirmPayment(
  slug: string,
  orderId: string
): Promise<OrderResponse> {
  return apiFetch<OrderResponse>(
    `/api/order/${slug}/confirm-payment/${orderId}/`,
    { method: "POST" }
  );
}

export async function saveCardConsent(
  slug: string,
  orderId: string
): Promise<void> {
  await apiFetch(`/api/order/${slug}/save-card/${orderId}/`, {
    method: "PATCH",
  });
}

// ── Queue ──
export interface QueueInfo {
  busyness: "green" | "yellow" | "red";
  estimated_wait_minutes: number;
  active_orders: number;
}

export interface OrderQueueInfo {
  queue_position: number | null;
  estimated_wait_minutes: number | null;
  status: string;
  busyness: string | null;
}

export async function fetchQueueInfo(slug: string): Promise<QueueInfo> {
  return apiFetch<QueueInfo>(`/api/order/${slug}/queue-info/`);
}

export async function fetchOrderQueue(slug: string, orderId: string): Promise<OrderQueueInfo> {
  return apiFetch<OrderQueueInfo>(`/api/order/${slug}/queue/${orderId}/`);
}

// ── Restaurant Admin ──
export async function fetchRestaurantOrders(
  slug: string
): Promise<OrderResponse[]> {
  return apiFetch<OrderResponse[]>(`/api/restaurants/${slug}/orders/`);
}

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
    { method: "POST", body: JSON.stringify({ plan, interval }) }
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

export async function cancelSubscription(
  slug: string
): Promise<Subscription> {
  return apiFetch<Subscription>(
    `/api/restaurants/${slug}/subscription/cancel/`,
    { method: "POST" }
  );
}

export async function reactivateSubscription(
  slug: string
): Promise<Subscription> {
  return apiFetch<Subscription>(
    `/api/restaurants/${slug}/subscription/reactivate/`,
    { method: "POST" }
  );
}

// ── POS Integration ──
export async function fetchPOSConnection(
  slug: string
): Promise<POSConnectionResponse> {
  return apiFetch<POSConnectionResponse>(
    `/api/restaurants/${slug}/pos/connection/`
  );
}

export async function initiatePOSConnect(
  slug: string,
  posType: string
): Promise<{ auth_url: string }> {
  return apiFetch<{ auth_url: string }>(
    `/api/restaurants/${slug}/pos/connect/`,
    { method: "POST", body: JSON.stringify({ pos_type: posType }) }
  );
}

export async function disconnectPOS(slug: string): Promise<void> {
  await apiFetch(`/api/restaurants/${slug}/pos/connection/`, {
    method: "DELETE",
  });
}

export async function updatePOSConnection(
  slug: string,
  data: { payment_mode?: string; external_location_id?: string }
): Promise<POSConnectionResponse> {
  return apiFetch<POSConnectionResponse>(
    `/api/restaurants/${slug}/pos/connection/`,
    { method: "PATCH", body: JSON.stringify(data) }
  );
}

export async function fetchPOSSyncLogs(
  slug: string,
  statusFilter?: string
): Promise<POSSyncLog[]> {
  const query = statusFilter ? `?status=${statusFilter}` : "";
  return apiFetch<POSSyncLog[]>(
    `/api/restaurants/${slug}/pos/sync-logs/${query}`
  );
}

export async function retryPOSSync(
  slug: string,
  orderId: string
): Promise<{ status: string }> {
  return apiFetch<{ status: string }>(
    `/api/restaurants/${slug}/pos/retry/${orderId}/`,
    { method: "POST" }
  );
}

export async function retryAllPOSSync(
  slug: string
): Promise<{ status: string; count: number }> {
  return apiFetch<{ status: string; count: number }>(
    `/api/restaurants/${slug}/pos/retry-all/`,
    { method: "POST" }
  );
}

export async function markSyncResolved(
  slug: string,
  logId: string
): Promise<POSSyncLog> {
  return apiFetch<POSSyncLog>(
    `/api/restaurants/${slug}/pos/sync-logs/${logId}/`,
    { method: "PATCH", body: JSON.stringify({ status: "manually_resolved" }) }
  );
}

// ── Menu Upload & Versions ──
export async function parseMenuImages(slug: string, images: File[]): Promise<ParsedMenu> {
  const formData = new FormData();
  images.forEach((img) => formData.append("images", img));
  return apiFetch<ParsedMenu>(`/api/restaurants/${slug}/menu/upload/parse/`, {
    method: "POST",
    body: formData,
  });
}

export async function saveUploadedMenu(
  slug: string,
  menu: ParsedMenu,
  mode: "overwrite" | "append",
  versionName?: string
): Promise<MenuVersion> {
  return apiFetch<MenuVersion>(`/api/restaurants/${slug}/menu/upload/save/`, {
    method: "POST",
    body: JSON.stringify({ menu, mode, version_name: versionName || "" }),
  });
}

export async function fetchMenuVersions(slug: string): Promise<MenuVersion[]> {
  return apiFetch<MenuVersion[]>(`/api/restaurants/${slug}/menu/versions/`);
}

export async function activateMenuVersion(slug: string, versionId: number): Promise<MenuVersion> {
  return apiFetch<MenuVersion>(`/api/restaurants/${slug}/menu/versions/${versionId}/activate/`, {
    method: "POST",
  });
}

export async function renameMenuVersion(slug: string, versionId: number, name: string): Promise<MenuVersion> {
  return apiFetch<MenuVersion>(`/api/restaurants/${slug}/menu/versions/${versionId}/`, {
    method: "PATCH",
    body: JSON.stringify({ name }),
  });
}

export async function deleteMenuVersion(slug: string, versionId: number): Promise<void> {
  return apiFetch<void>(`/api/restaurants/${slug}/menu/versions/${versionId}/`, {
    method: "DELETE",
  });
}

// ── Onboarding ──
export async function completeOnboarding(): Promise<{ status: string }> {
  return apiFetch("/api/account/onboarding/complete/", { method: "POST" });
}

export async function dismissOnboarding(): Promise<{ status: string }> {
  return apiFetch("/api/account/onboarding/dismiss/", { method: "POST" });
}
