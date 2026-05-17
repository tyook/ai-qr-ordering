import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchOperatingHours,
  saveOperatingHours,
  fetchHolidayOverrides,
  createHolidayOverride,
  deleteHolidayOverride,
} from "@/lib/api";
import type { OperatingHoursEntry, HolidayOverride } from "@/types";

export function useOperatingHours(slug: string) {
  return useQuery({
    queryKey: ["operating-hours", slug],
    queryFn: () => fetchOperatingHours(slug),
    enabled: !!slug,
  });
}

export function useSaveOperatingHours(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: OperatingHoursEntry[]) => saveOperatingHours(slug, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["operating-hours", slug] });
    },
  });
}

export function useHolidayOverrides(slug: string) {
  return useQuery({
    queryKey: ["holiday-overrides", slug],
    queryFn: () => fetchHolidayOverrides(slug),
    enabled: !!slug,
  });
}

export function useCreateHolidayOverride(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: Omit<HolidayOverride, "id">) => createHolidayOverride(slug, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["holiday-overrides", slug] });
    },
  });
}

export function useDeleteHolidayOverride(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deleteHolidayOverride(slug, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["holiday-overrides", slug] });
    },
  });
}
