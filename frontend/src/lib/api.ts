import { isNativePlatform } from "./native";
import { getAccessToken, getRefreshToken, setTokens, clearTokens } from "./token-storage";

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
    if (isNativePlatform()) {
      const refreshToken = await getRefreshToken();
      if (!refreshToken) return false;
      const resp = await fetch(`${API_URL}/api/auth/refresh/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (resp.ok) {
        const data = await resp.json();
        if (data.access_token && data.refresh_token) {
          await setTokens(data.access_token, data.refresh_token);
        }
        return true;
      }
      await clearTokens();
      return false;
    } else {
      const resp = await fetch(`${API_URL}/api/auth/refresh/`, {
        method: "POST",
        credentials: "include",
      });
      return resp.ok;
    }
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

  if (isNativePlatform()) {
    const token = await getAccessToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  } else {
    // existing CSRF logic (only for web)
    if (method !== "GET" && method !== "HEAD") {
      const csrfToken = getCookie("csrftoken");
      if (csrfToken) {
        headers["X-CSRFToken"] = csrfToken;
      }
    }
  }

  const response = await fetch(url, {
    ...options,
    headers,
    ...(isNativePlatform() ? {} : { credentials: "include" as RequestCredentials }),
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

  if (response.status === 403) {
    const error = await response.json().catch(() => ({}));
    if (
      error.code === "permission_denied" &&
      typeof error.detail === "string" &&
      error.detail.toLowerCase().includes("subscription")
    ) {
      if (typeof window !== "undefined") {
        const slugMatch = path.match(/\/api\/restaurants\/([^/]+)\//);
        const slug = slugMatch?.[1];
        if (slug) {
          window.location.href = `/account/restaurants/${slug}/billing`;
          return new Promise<T>(() => {}); // never resolves; page is navigating
        }
      }
    }
    throw new Error(error.detail || `API error: 403`);
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
  MenuUnavailable,
  ParseOrderResult,
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
  CartUpsellResponse,
  TabResponse,
  TabOrderResponse,
  TabPaymentResponse,
  TeamResponse,
  TeamInvitation,
  StaffMember,
  MyRoleResponse,
  InvitationDetail,
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
export async function fetchMenu(slug: string): Promise<PublicMenu | MenuUnavailable> {
  return apiFetch<PublicMenu | MenuUnavailable>(`/api/order/${slug}/menu/`);
}

export async function parseOrder(
  slug: string,
  rawInput: string
): Promise<ParseOrderResult> {
  return apiFetch<ParseOrderResult>(`/api/order/${slug}/parse/`, {
    method: "POST",
    body: JSON.stringify({ raw_input: rawInput }),
  });
}

export async function transcribeAudio(
  slug: string,
  audioBlob: Blob
): Promise<string> {
  const formData = new FormData();
  formData.append("audio", audioBlob, "recording.webm");
  const result = await apiFetch<{ transcript: string }>(
    `/api/order/${slug}/transcribe/`,
    {
      method: "POST",
      body: formData,
    }
  );
  return result.transcript;
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

// ── Tab ──
export async function fetchTab(
  slug: string,
  tableIdentifier: string
): Promise<TabResponse | null> {
  try {
    return await apiFetch<TabResponse>(
      `/api/order/${slug}/tab/?table=${encodeURIComponent(tableIdentifier)}`
    );
  } catch {
    return null;
  }
}

export async function createTabOrder(
  slug: string,
  items: ConfirmOrderItem[],
  rawInput: string,
  tableIdentifier: string,
  language: string,
  customerName?: string,
  customerPhone?: string,
  allergies?: string[]
): Promise<TabOrderResponse> {
  return apiFetch<TabOrderResponse>(`/api/order/${slug}/tab/order/`, {
    method: "POST",
    body: JSON.stringify({
      items,
      raw_input: rawInput,
      table_identifier: tableIdentifier,
      language,
      customer_name: customerName || "",
      customer_phone: customerPhone || "",
      allergies: allergies || [],
    }),
  });
}

export async function closeTab(
  slug: string,
  tableIdentifier: string
): Promise<TabResponse> {
  return apiFetch<TabResponse>(`/api/order/${slug}/tab/close/`, {
    method: "POST",
    body: JSON.stringify({ table_identifier: tableIdentifier }),
  });
}

export async function createTabPayment(
  slug: string,
  tabId: string,
  type: "full" | "split_even" | "pay_by_item",
  splitCount?: number,
  itemIds?: number[]
): Promise<TabPaymentResponse> {
  return apiFetch<TabPaymentResponse>(`/api/order/${slug}/tab/pay/`, {
    method: "POST",
    body: JSON.stringify({
      tab_id: tabId,
      type,
      split_count: splitCount,
      item_ids: itemIds,
    }),
  });
}

export async function confirmTabPayment(
  slug: string,
  paymentId: string
): Promise<TabResponse> {
  return apiFetch<TabResponse>(
    `/api/order/${slug}/tab/confirm-payment/${paymentId}/`,
    { method: "POST" }
  );
}

// ── Upsell ──
export async function fetchCartUpsell(
  slug: string,
  items: { menu_item_id: number; variant_id: number; quantity: number }[]
): Promise<CartUpsellResponse> {
  return apiFetch<CartUpsellResponse>(`/api/order/${slug}/cart-upsell/`, {
    method: "POST",
    body: JSON.stringify({ items }),
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

export async function selectPOSVendor(
  slug: string,
  posType: string
): Promise<POSConnectionResponse> {
  return apiFetch<POSConnectionResponse>(
    `/api/restaurants/${slug}/pos/select-vendor/`,
    { method: "POST", body: JSON.stringify({ pos_type: posType }) }
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

// ── Connect Onboarding ──
export async function createOnboardingConnectLink(
  slug: string,
  returnUrl: string,
  refreshUrl: string
): Promise<{ url: string }> {
  return apiFetch<{ url: string }>(
    `/api/restaurants/${slug}/connect/onboarding-initiate/`,
    {
      method: "POST",
      body: JSON.stringify({ return_url: returnUrl, refresh_url: refreshUrl }),
    }
  );
}

export async function fetchOnboardingConnectStatus(
  slug: string
): Promise<{
  has_account: boolean;
  onboarding_complete: boolean;
  payouts_enabled: boolean;
  charges_enabled: boolean;
}> {
  return apiFetch(
    `/api/restaurants/${slug}/connect/onboarding-status/`
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

export async function uploadMenuItemImage(
  slug: string,
  image: File
): Promise<{ image_url: string }> {
  const formData = new FormData();
  formData.append("image", image);
  return apiFetch<{ image_url: string }>(`/api/restaurants/${slug}/menu/upload/image/`, {
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

// ── Tables ──
import type { Table } from "@/types";

export async function fetchTables(slug: string): Promise<Table[]> {
  return apiFetch<Table[]>(`/api/restaurants/${slug}/tables/`);
}

export async function createTable(
  slug: string,
  data: { name: string; number: string }
): Promise<Table> {
  return apiFetch<Table>(`/api/restaurants/${slug}/tables/`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateTable(
  slug: string,
  tableId: string,
  data: Partial<{ name: string; number: string; is_active: boolean }>
): Promise<Table> {
  return apiFetch<Table>(`/api/restaurants/${slug}/tables/${tableId}/`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteTable(
  slug: string,
  tableId: string
): Promise<void> {
  return apiFetch<void>(`/api/restaurants/${slug}/tables/${tableId}/`, {
    method: "DELETE",
  });
}

// ── Accepting Orders ──
export interface AcceptingOrdersStatus {
  accepting_orders: boolean;
  auto_resume_orders: boolean;
}

export async function fetchAcceptingOrders(slug: string): Promise<AcceptingOrdersStatus> {
  return apiFetch<AcceptingOrdersStatus>(`/api/restaurants/${slug}/accepting-orders/`);
}

export async function toggleAcceptingOrders(
  slug: string,
  data: { accepting_orders: boolean; auto_resume_orders?: boolean }
): Promise<AcceptingOrdersStatus> {
  return apiFetch<AcceptingOrdersStatus>(`/api/restaurants/${slug}/accepting-orders/`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ── Operating Hours ──
import type { OperatingHoursEntry, HolidayOverride } from "@/types";

export async function fetchOperatingHours(slug: string): Promise<OperatingHoursEntry[]> {
  return apiFetch<OperatingHoursEntry[]>(`/api/restaurants/${slug}/operating-hours/`);
}

export async function saveOperatingHours(
  slug: string,
  data: OperatingHoursEntry[]
): Promise<OperatingHoursEntry[]> {
  return apiFetch<OperatingHoursEntry[]>(`/api/restaurants/${slug}/operating-hours/`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function fetchHolidayOverrides(slug: string): Promise<HolidayOverride[]> {
  return apiFetch<HolidayOverride[]>(`/api/restaurants/${slug}/holiday-overrides/`);
}

export async function createHolidayOverride(
  slug: string,
  data: Omit<HolidayOverride, "id">
): Promise<HolidayOverride> {
  return apiFetch<HolidayOverride>(`/api/restaurants/${slug}/holiday-overrides/`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function deleteHolidayOverride(
  slug: string,
  id: number
): Promise<void> {
  return apiFetch<void>(`/api/restaurants/${slug}/holiday-overrides/${id}/`, {
    method: "DELETE",
  });
}

// ── Hall Status ──
import type { HallStatusTable } from "@/types";

export async function fetchHallStatus(slug: string): Promise<HallStatusTable[]> {
  return apiFetch<HallStatusTable[]>(`/api/restaurants/${slug}/hall-status/`);
}

// ── Analytics ──
import type { AnalyticsResponse } from "@/types";

export async function fetchAnalytics(
  slug: string,
  period: string = "30d",
  startDate?: string,
  endDate?: string
): Promise<AnalyticsResponse> {
  const params = new URLSearchParams({ period });
  if (period === "custom" && startDate && endDate) {
    params.set("start_date", startDate);
    params.set("end_date", endDate);
  }
  return apiFetch<AnalyticsResponse>(
    `/api/restaurants/${slug}/analytics/?${params.toString()}`
  );
}

// ── Billing History ──
import type { BillingInvoice } from "@/types";

export async function fetchBillingHistory(slug: string): Promise<BillingInvoice[]> {
  return apiFetch<BillingInvoice[]>(`/api/restaurants/${slug}/subscription/invoices/`);
}

// ── Onboarding ──
export async function completeOnboarding(): Promise<{ status: string }> {
  return apiFetch("/api/account/onboarding/complete/", { method: "POST" });
}

export async function dismissOnboarding(): Promise<{ status: string }> {
  return apiFetch("/api/account/onboarding/dismiss/", { method: "POST" });
}

// Team Management
export async function fetchTeam(slug: string): Promise<TeamResponse> {
  return apiFetch<TeamResponse>(`/api/restaurants/${slug}/team/`);
}

export async function inviteTeamMember(
  slug: string,
  data: { email: string; role: string; permissions?: Record<string, boolean> }
): Promise<TeamInvitation> {
  return apiFetch<TeamInvitation>(`/api/restaurants/${slug}/team/invite/`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateTeamMember(
  slug: string,
  staffId: number,
  data: { role?: string; permissions?: Record<string, boolean> }
): Promise<StaffMember> {
  return apiFetch<StaffMember>(`/api/restaurants/${slug}/team/${staffId}/`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function removeTeamMember(slug: string, staffId: number): Promise<void> {
  return apiFetch<void>(`/api/restaurants/${slug}/team/${staffId}/`, {
    method: "DELETE",
  });
}

export async function transferOwnership(slug: string, newOwnerId: string): Promise<void> {
  return apiFetch<void>(`/api/restaurants/${slug}/team/transfer-ownership/`, {
    method: "POST",
    body: JSON.stringify({ new_owner_id: newOwnerId }),
  });
}

export async function resendInvitation(slug: string, invitationId: string): Promise<TeamInvitation> {
  return apiFetch<TeamInvitation>(`/api/restaurants/${slug}/team/invitations/${invitationId}/resend/`, {
    method: "POST",
  });
}

export async function revokeInvitation(slug: string, invitationId: string): Promise<void> {
  return apiFetch<void>(`/api/restaurants/${slug}/team/invitations/${invitationId}/`, {
    method: "DELETE",
  });
}

export async function fetchMyRole(slug: string): Promise<MyRoleResponse> {
  return apiFetch<MyRoleResponse>(`/api/restaurants/${slug}/my-role/`);
}

export async function fetchInvitationDetail(token: string): Promise<InvitationDetail> {
  return apiFetch<InvitationDetail>(`/api/invitations/${token}/`);
}

export async function acceptInvitation(
  token: string,
  data?: { first_name?: string; last_name?: string; password?: string }
): Promise<{ detail: string; restaurant_slug: string; role: string }> {
  return apiFetch(`/api/invitations/${token}/accept/`, {
    method: "POST",
    body: JSON.stringify(data || {}),
  });
}
