import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchSubscription,
  createCheckoutSession,
  createBillingPortal,
  cancelSubscription,
  reactivateSubscription,
} from "@/lib/api";

export function useSubscription(slug: string) {
  return useQuery({
    queryKey: ["subscription", slug],
    queryFn: () => fetchSubscription(slug),
    enabled: !!slug,
  });
}

export function useCreateCheckout(slug: string) {
  return useMutation({
    mutationFn: ({ plan, interval }: { plan: string; interval: "monthly" | "annual" }) =>
      createCheckoutSession(slug, plan, interval),
    onSuccess: (data) => {
      window.location.href = data.checkout_url;
    },
  });
}

export function useCreateBillingPortal(slug: string) {
  return useMutation({
    mutationFn: () => createBillingPortal(slug),
    onSuccess: (data) => {
      window.location.href = data.portal_url;
    },
  });
}

export function useCancelSubscription(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => cancelSubscription(slug),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["subscription", slug] });
    },
  });
}

export function useReactivateSubscription(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => reactivateSubscription(slug),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["subscription", slug] });
    },
  });
}
