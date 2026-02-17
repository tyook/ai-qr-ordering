import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { Restaurant } from "@/types";

export function useMyRestaurants(enabled = true) {
  return useQuery({
    queryKey: ["my-restaurants"],
    queryFn: () =>
      apiFetch<{ results: Restaurant[] }>("/api/restaurants/me/").then(
        (data) => data.results
      ),
    enabled,
  });
}
