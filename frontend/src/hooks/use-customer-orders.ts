import { useQuery } from "@tanstack/react-query";
import { fetchCustomerOrders } from "@/lib/api";

export function useCustomerOrders() {
  return useQuery({
    queryKey: ["customer-orders"],
    queryFn: fetchCustomerOrders,
  });
}
