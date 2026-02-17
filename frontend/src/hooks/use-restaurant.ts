import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { Restaurant } from "@/types";

export function useRestaurant(slug: string) {
  return useQuery({
    queryKey: ["restaurant", slug],
    queryFn: () => apiFetch<Restaurant>(`/api/restaurants/${slug}/`),
    enabled: !!slug,
  });
}
