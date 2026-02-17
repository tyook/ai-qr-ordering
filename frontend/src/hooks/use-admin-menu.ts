import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

interface Variant {
  id: number;
  label: string;
  price: string;
  is_default: boolean;
}

interface Modifier {
  id: number;
  name: string;
  price_adjustment: string;
}

interface MenuItemFull {
  id: number;
  name: string;
  description: string;
  is_active: boolean;
  sort_order: number;
  variants: Variant[];
  modifiers: Modifier[];
}

interface Category {
  id: number;
  name: string;
  sort_order: number;
  is_active: boolean;
  items: MenuItemFull[];
}

export interface AdminMenu {
  restaurant_name: string;
  categories: Category[];
}

export function useAdminMenu(slug: string, enabled = true) {
  return useQuery({
    queryKey: ["admin-menu", slug],
    queryFn: () => apiFetch<AdminMenu>(`/api/restaurants/${slug}/menu/`),
    enabled: !!slug && enabled,
  });
}

export function useAddCategory(slug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (params: { name: string; sort_order: number }) =>
      apiFetch(`/api/restaurants/${slug}/categories/`, {
        method: "POST",
        body: JSON.stringify(params),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-menu", slug] });
    },
  });
}

export function useAddMenuItem(slug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (params: {
      category_id: number;
      name: string;
      description: string;
      sort_order: number;
      variants: { label: string; price: string; is_default: boolean }[];
      modifiers: unknown[];
    }) =>
      apiFetch(`/api/restaurants/${slug}/items/`, {
        method: "POST",
        body: JSON.stringify(params),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-menu", slug] });
    },
  });
}

export function useDeactivateMenuItem(slug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (itemId: number) =>
      apiFetch(`/api/restaurants/${slug}/items/${itemId}/`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-menu", slug] });
    },
  });
}
