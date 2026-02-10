const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5005";

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
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
  language: string
): Promise<OrderResponse> {
  return apiFetch<OrderResponse>(`/api/order/${slug}/confirm/`, {
    method: "POST",
    body: JSON.stringify({
      items,
      raw_input: rawInput,
      table_identifier: tableIdentifier,
      language,
    }),
  });
}

export async function fetchOrderStatus(
  slug: string,
  orderId: string
): Promise<OrderResponse> {
  return apiFetch<OrderResponse>(`/api/order/${slug}/status/${orderId}/`);
}

