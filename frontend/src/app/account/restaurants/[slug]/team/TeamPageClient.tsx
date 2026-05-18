"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Plus, Users } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useRequireRestaurantAccess } from "@/hooks/use-auth";
import {
  useTeam,
  useInviteTeamMember,
  useUpdateTeamMember,
  useRemoveTeamMember,
  useTransferOwnership,
  useResendInvitation,
  useRevokeInvitation,
} from "@/hooks/use-team";
import { useMyRole } from "@/hooks/use-my-role";
import { useToast } from "@/hooks/use-toast";
import { useAuthStore } from "@/stores/auth-store";
import { MemberRow } from "./components/member-row";
import { PendingInviteRow } from "./components/pending-invite-row";
import { InviteModal } from "./components/invite-modal";

export default function TeamPageClient() {
  const params = useParams();
  const slug = params.slug as string;
  const isAuthenticated = useRequireRestaurantAccess();
  const { toast } = useToast();
  const user = useAuthStore((s) => s.user);

  const { data: team, isLoading, error } = useTeam(slug);
  const { data: myRole } = useMyRole(slug);

  const [inviteModalOpen, setInviteModalOpen] = useState(false);

  const inviteMember = useInviteTeamMember(slug);
  const updateMember = useUpdateTeamMember(slug);
  const removeMember = useRemoveTeamMember(slug);
  const transferOwnership = useTransferOwnership(slug);
  const resendInvitation = useResendInvitation(slug);
  const revokeInvitation = useRevokeInvitation(slug);

  const isAdmin = myRole?.is_admin ?? false;

  function handleInvite(data: {
    email: string;
    role: string;
    permissions?: Record<string, boolean>;
  }) {
    inviteMember.mutate(data, {
      onSuccess: () => {
        toast({ title: "Invitation sent", description: `Invited ${data.email} as ${data.role}.` });
        setInviteModalOpen(false);
      },
      onError: (err) => {
        toast({
          title: "Failed to send invitation",
          description: err instanceof Error ? err.message : "An error occurred.",
          variant: "destructive",
        });
      },
    });
  }

  function handleUpdateRole(staffId: number, role: string) {
    updateMember.mutate(
      { staffId, data: { role } },
      {
        onSuccess: () => {
          toast({ title: "Role updated", description: `Team member role changed to ${role}.` });
        },
        onError: (err) => {
          toast({
            title: "Failed to update role",
            description: err instanceof Error ? err.message : "An error occurred.",
            variant: "destructive",
          });
        },
      }
    );
  }

  function handleUpdatePermissions(staffId: number, permissions: Record<string, boolean>) {
    updateMember.mutate(
      { staffId, data: { permissions } },
      {
        onSuccess: () => {
          toast({ title: "Permissions updated", description: "Team member permissions have been updated." });
        },
        onError: (err) => {
          toast({
            title: "Failed to update permissions",
            description: err instanceof Error ? err.message : "An error occurred.",
            variant: "destructive",
          });
        },
      }
    );
  }

  function handleRemoveMember(staffId: number) {
    removeMember.mutate(staffId, {
      onSuccess: () => {
        toast({ title: "Member removed", description: "Team member has been removed." });
      },
      onError: (err) => {
        toast({
          title: "Failed to remove member",
          description: err instanceof Error ? err.message : "An error occurred.",
          variant: "destructive",
        });
      },
    });
  }

  function handleTransferOwnership(newOwnerId: string) {
    transferOwnership.mutate(newOwnerId, {
      onSuccess: () => {
        toast({ title: "Ownership transferred", description: "Restaurant ownership has been transferred." });
      },
      onError: (err) => {
        toast({
          title: "Failed to transfer ownership",
          description: err instanceof Error ? err.message : "An error occurred.",
          variant: "destructive",
        });
      },
    });
  }

  function handleResendInvitation(invitationId: string) {
    resendInvitation.mutate(invitationId, {
      onSuccess: () => {
        toast({ title: "Invitation resent", description: "The invitation email has been resent." });
      },
      onError: (err) => {
        toast({
          title: "Failed to resend invitation",
          description: err instanceof Error ? err.message : "An error occurred.",
          variant: "destructive",
        });
      },
    });
  }

  function handleRevokeInvitation(invitationId: string) {
    revokeInvitation.mutate(invitationId, {
      onSuccess: () => {
        toast({ title: "Invitation revoked", description: "The invitation has been revoked." });
      },
      onError: (err) => {
        toast({
          title: "Failed to revoke invitation",
          description: err instanceof Error ? err.message : "An error occurred.",
          variant: "destructive",
        });
      },
    });
  }

  if (isAuthenticated === null || (isLoading && !team)) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (isAuthenticated === false) {
    return null;
  }

  const members = team?.members ?? [];
  const pendingInvitations = (team?.invitations ?? []).filter(
    (inv) => inv.status === "pending"
  );

  // Sort: owner first, then admins, then members
  const sortedMembers = [...members].sort((a, b) => {
    const order = { owner: 0, admin: 1, member: 2 };
    return order[a.role] - order[b.role];
  });

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-3xl mx-auto">
        <Link
          href="/account/restaurants"
          className="text-sm text-muted-foreground hover:underline"
        >
          Back to dashboard
        </Link>

        <div className="flex items-center justify-between mt-2 mb-6 flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <Users className="h-6 w-6" />
            <h1 className="text-2xl font-bold">Team</h1>
          </div>
          {isAdmin && (
            <Button onClick={() => setInviteModalOpen(true)}>
              <Plus className="h-4 w-4 mr-1.5" />
              Invite Member
            </Button>
          )}
        </div>

        {error ? (
          <div className="text-center py-12">
            <p className="text-destructive">Failed to load team.</p>
            <p className="text-sm text-muted-foreground mt-2">
              {error instanceof Error ? error.message : "Unknown error"}
            </p>
          </div>
        ) : (
          <>
            {/* Team members */}
            <Card className="bg-card border border-border rounded-2xl overflow-hidden">
              <div className="px-4 py-3 border-b border-border">
                <h2 className="text-sm font-semibold text-muted-foreground">
                  Members ({members.length})
                </h2>
              </div>
              {sortedMembers.length === 0 ? (
                <div className="py-8 text-center text-sm text-muted-foreground">
                  No team members yet.
                </div>
              ) : (
                <div className="divide-y divide-border">
                  {sortedMembers.map((member) => (
                    <MemberRow
                      key={member.id}
                      member={member}
                      myRole={myRole}
                      currentUserId={user?.id}
                      allMembers={members}
                      onUpdateRole={handleUpdateRole}
                      onUpdatePermissions={handleUpdatePermissions}
                      onRemove={handleRemoveMember}
                      onTransferOwnership={handleTransferOwnership}
                    />
                  ))}
                </div>
              )}
            </Card>

            {/* Pending invitations */}
            {isAdmin && pendingInvitations.length > 0 && (
              <>
                <Separator className="my-6" />
                <Card className="bg-card border border-border rounded-2xl overflow-hidden">
                  <div className="px-4 py-3 border-b border-border">
                    <h2 className="text-sm font-semibold text-muted-foreground">
                      Pending invitations ({pendingInvitations.length})
                    </h2>
                  </div>
                  <div className="divide-y divide-border">
                    {pendingInvitations.map((invitation) => (
                      <PendingInviteRow
                        key={invitation.id}
                        invitation={invitation}
                        onResend={handleResendInvitation}
                        onRevoke={handleRevokeInvitation}
                        isResending={resendInvitation.isPending && resendInvitation.variables === invitation.id}
                        isRevoking={revokeInvitation.isPending && revokeInvitation.variables === invitation.id}
                      />
                    ))}
                  </div>
                </Card>
              </>
            )}
          </>
        )}

        <InviteModal
          open={inviteModalOpen}
          onOpenChange={setInviteModalOpen}
          onInvite={handleInvite}
          isLoading={inviteMember.isPending}
        />
      </div>
    </div>
  );
}
