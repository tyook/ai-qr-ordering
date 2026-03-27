import { useMutation, useQueryClient } from "@tanstack/react-query";
import { completeOnboarding, dismissOnboarding } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";

export function useCompleteOnboarding() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: completeOnboarding,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profile"] });
      useAuthStore.getState().checkAuth();
    },
  });
}

export function useDismissOnboarding() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: dismissOnboarding,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profile"] });
      useAuthStore.getState().checkAuth();
    },
  });
}
