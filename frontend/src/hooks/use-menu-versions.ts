import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchMenuVersions,
  activateMenuVersion,
  renameMenuVersion,
  deleteMenuVersion,
} from "@/lib/api";

export function useMenuVersions(slug: string) {
  return useQuery({
    queryKey: ["menu-versions", slug],
    queryFn: () => fetchMenuVersions(slug),
    enabled: !!slug,
  });
}

export function useActivateVersion(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (versionId: number) => activateMenuVersion(slug, versionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["menu-versions", slug] });
      queryClient.invalidateQueries({ queryKey: ["admin-menu", slug] });
    },
  });
}

export function useRenameVersion(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ versionId, name }: { versionId: number; name: string }) =>
      renameMenuVersion(slug, versionId, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["menu-versions", slug] });
    },
  });
}

export function useDeleteVersion(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (versionId: number) => deleteMenuVersion(slug, versionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["menu-versions", slug] });
      queryClient.invalidateQueries({ queryKey: ["admin-menu", slug] });
    },
  });
}
