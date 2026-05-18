import { useQuery } from "@tanstack/react-query";
import { fetchMyRole } from "@/lib/api";
import type { MyRoleResponse } from "@/types";

export function useMyRole(slug: string) {
  return useQuery({
    queryKey: ["my-role", slug],
    queryFn: () => fetchMyRole(slug),
    enabled: !!slug,
  });
}

export function useCan(slug: string) {
  const { data: role } = useMyRole(slug);
  return (permission: string): boolean => {
    if (!role) return false;
    if (role.is_admin) return true;
    return (role as unknown as Record<string, unknown>)[permission] === true;
  };
}
