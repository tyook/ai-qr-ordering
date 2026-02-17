import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export function useUpdateTaxRate(slug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (taxRate: string) =>
      apiFetch(`/api/restaurants/${slug}/`, {
        method: "PATCH",
        body: JSON.stringify({ tax_rate: taxRate }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["restaurant", slug] });
    },
  });
}
