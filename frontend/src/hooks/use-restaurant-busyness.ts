import { useQuery } from "@tanstack/react-query";
import { fetchQueueInfo, type QueueInfo } from "@/lib/api";

export function useRestaurantBusyness(slug: string) {
  const { data, isLoading, error } = useQuery<QueueInfo>({
    queryKey: ["queueInfo", slug],
    queryFn: () => fetchQueueInfo(slug),
    refetchInterval: 60_000,
    retry: 1,
  });

  return {
    busyness: data?.busyness ?? null,
    estimatedWait: data?.estimated_wait_minutes ?? null,
    activeOrders: data?.active_orders ?? 0,
    isLoading,
    error,
  };
}
