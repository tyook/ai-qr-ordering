"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { cn } from "@/lib/utils";
import type { TeamInvitation } from "@/types";

const ROLE_BADGE_CLASSES: Record<string, string> = {
  admin: "bg-blue-100 text-blue-800 border-blue-200",
  member: "bg-gray-100 text-gray-800 border-gray-200",
};

interface PendingInviteRowProps {
  invitation: TeamInvitation;
  onResend: (invitationId: string) => void;
  onRevoke: (invitationId: string) => void;
  isResending?: boolean;
  isRevoking?: boolean;
}

export function PendingInviteRow({
  invitation,
  onResend,
  onRevoke,
  isResending,
  isRevoking,
}: PendingInviteRowProps) {
  const [revokeConfirmOpen, setRevokeConfirmOpen] = useState(false);

  const isExpired = new Date(invitation.expires_at) < new Date();
  const createdDate = new Date(invitation.created_at).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  return (
    <>
      <div className="flex items-center justify-between py-3 px-4">
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-muted text-sm font-medium shrink-0">
            {invitation.email[0].toUpperCase()}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm font-medium truncate">{invitation.email}</span>
              <Badge
                variant="outline"
                className={cn("text-xs capitalize", ROLE_BADGE_CLASSES[invitation.role])}
              >
                {invitation.role}
              </Badge>
              {isExpired && (
                <Badge variant="outline" className="text-xs bg-red-50 text-red-700 border-red-200">
                  Expired
                </Badge>
              )}
            </div>
            <p className="text-xs text-muted-foreground">
              Invited by {invitation.invited_by_name} on {createdDate}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onResend(invitation.id)}
            disabled={isResending}
          >
            {isResending ? "Sending..." : "Resend"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="text-destructive hover:text-destructive"
            onClick={() => setRevokeConfirmOpen(true)}
            disabled={isRevoking}
          >
            {isRevoking ? "Revoking..." : "Revoke"}
          </Button>
        </div>
      </div>

      <AlertDialog open={revokeConfirmOpen} onOpenChange={setRevokeConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Revoke invitation</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to revoke the invitation for {invitation.email}? They
              will no longer be able to join the team with this invite link.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => {
                onRevoke(invitation.id);
                setRevokeConfirmOpen(false);
              }}
            >
              Revoke
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
