import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchPOSSyncLogs,
  markSyncResolved,
  retryAllPOSSync,
  retryPOSSync,
} from "@/lib/api";

export function usePOSSyncLogs(slug: string, statusFilter?: string) {
  return useQuery({
    queryKey: ["pos-sync-logs", slug, statusFilter],
    queryFn: () => fetchPOSSyncLogs(slug, statusFilter),
    enabled: !!slug,
    refetchInterval: 10000,
  });
}

export function useRetrySync(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (orderId: string) => retryPOSSync(slug, orderId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pos-sync-logs", slug] });
    },
  });
}

export function useRetryAllSync(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => retryAllPOSSync(slug),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pos-sync-logs", slug] });
    },
  });
}

export function useMarkResolved(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (logId: string) => markSyncResolved(slug, logId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pos-sync-logs", slug] });
    },
  });
}
