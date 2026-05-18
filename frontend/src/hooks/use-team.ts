import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchTeam,
  inviteTeamMember,
  updateTeamMember,
  removeTeamMember,
  transferOwnership,
  resendInvitation,
  revokeInvitation,
} from "@/lib/api";

export function useTeam(slug: string) {
  return useQuery({
    queryKey: ["team", slug],
    queryFn: () => fetchTeam(slug),
    enabled: !!slug,
  });
}

export function useInviteTeamMember(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { email: string; role: string; permissions?: Record<string, boolean> }) =>
      inviteTeamMember(slug, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["team", slug] }),
  });
}

export function useUpdateTeamMember(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ staffId, data }: { staffId: number; data: { role?: string; permissions?: Record<string, boolean> } }) =>
      updateTeamMember(slug, staffId, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["team", slug] }),
  });
}

export function useRemoveTeamMember(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (staffId: number) => removeTeamMember(slug, staffId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["team", slug] }),
  });
}

export function useTransferOwnership(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (newOwnerId: string) => transferOwnership(slug, newOwnerId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["team", slug] });
      queryClient.invalidateQueries({ queryKey: ["my-role", slug] });
    },
  });
}

export function useResendInvitation(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (invitationId: string) => resendInvitation(slug, invitationId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["team", slug] }),
  });
}

export function useRevokeInvitation(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (invitationId: string) => revokeInvitation(slug, invitationId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["team", slug] }),
  });
}
