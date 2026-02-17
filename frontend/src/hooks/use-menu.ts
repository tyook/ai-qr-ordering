import { useQuery } from "@tanstack/react-query";
import { fetchMenu } from "@/lib/api";

export function useMenu(slug: string) {
  return useQuery({
    queryKey: ["menu", slug],
    queryFn: () => fetchMenu(slug),
    enabled: !!slug,
  });
}
