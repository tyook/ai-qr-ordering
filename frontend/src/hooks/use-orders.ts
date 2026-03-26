import { useQuery } from "@tanstack/react-query";
import { fetchOrderHistory, fetchOrderDetail } from "@/lib/api";

export function useOrderHistory() {
  return useQuery({
    queryKey: ["orderHistory"],
    queryFn: fetchOrderHistory,
  });
}

export function useOrderDetail(orderId: string) {
  return useQuery({
    queryKey: ["orderDetail", orderId],
    queryFn: () => fetchOrderDetail(orderId),
    enabled: !!orderId,
  });
}
