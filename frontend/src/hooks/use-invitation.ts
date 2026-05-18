import { useQuery, useMutation } from "@tanstack/react-query";
import { fetchInvitationDetail, acceptInvitation } from "@/lib/api";

export function useInvitationDetail(token: string) {
  return useQuery({
    queryKey: ["invitation", token],
    queryFn: () => fetchInvitationDetail(token),
    enabled: !!token,
  });
}

export function useAcceptInvitation(token: string) {
  return useMutation({
    mutationFn: (data?: { first_name?: string; last_name?: string; password?: string }) =>
      acceptInvitation(token, data),
  });
}
