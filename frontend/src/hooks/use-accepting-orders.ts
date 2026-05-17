import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchAcceptingOrders, toggleAcceptingOrders } from "@/lib/api";
import type { AcceptingOrdersStatus } from "@/lib/api";

export function useAcceptingOrders(slug: string, enabled = true) {
  return useQuery({
    queryKey: ["accepting-orders", slug],
    queryFn: () => fetchAcceptingOrders(slug),
    enabled: !!slug && enabled,
  });
}

export function useToggleAcceptingOrders(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { accepting_orders: boolean; auto_resume_orders?: boolean }) =>
      toggleAcceptingOrders(slug, data),
    onSuccess: (data: AcceptingOrdersStatus) => {
      queryClient.setQueryData(["accepting-orders", slug], data);
    },
  });
}
