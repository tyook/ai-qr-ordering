import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { Restaurant } from "@/types";

interface CreateRestaurantParams {
  name: string;
  slug: string;
  phone?: string;
  address?: string;
  homepage?: string;
  logo_url?: string;
}

export function useCreateRestaurant() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (params: CreateRestaurantParams) => {
      const body: Record<string, string> = {
        name: params.name,
        slug: params.slug,
      };
      if (params.phone) body.phone = params.phone;
      if (params.address) body.address = params.address;
      if (params.homepage) body.homepage = params.homepage;
      if (params.logo_url) body.logo_url = params.logo_url;

      return apiFetch<Restaurant>("/api/restaurants/", {
        method: "POST",
        body: JSON.stringify(body),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["my-restaurants"] });
    },
  });
}
