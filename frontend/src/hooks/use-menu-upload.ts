import { useMutation, useQueryClient } from "@tanstack/react-query";
import { parseMenuImages, saveUploadedMenu } from "@/lib/api";
import type { ParsedMenu } from "@/types";

export function useParseMenuImages(slug: string) {
  return useMutation({
    mutationFn: (images: File[]) => parseMenuImages(slug, images),
  });
}

export function useSaveUploadedMenu(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      menu,
      mode,
      versionName,
    }: {
      menu: ParsedMenu;
      mode: "overwrite" | "append";
      versionName?: string;
    }) => saveUploadedMenu(slug, menu, mode, versionName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["menu-versions", slug] });
      queryClient.invalidateQueries({ queryKey: ["admin-menu", slug] });
    },
  });
}
