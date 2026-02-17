import { useMutation } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { OrderResponse } from "@/types";

export function useAdvanceOrder() {
  return useMutation({
    mutationFn: (params: { orderId: string; nextStatus: string }) =>
      apiFetch<OrderResponse>(`/api/kitchen/orders/${params.orderId}/`, {
        method: "PATCH",
        body: JSON.stringify({ status: params.nextStatus }),
      }),
  });
}
