"use client";

import { useState } from "react";
import { MoreVertical } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import type { StaffMember, MyRoleResponse } from "@/types";

const ROLE_BADGE_CLASSES: Record<string, string> = {
  owner: "bg-amber-100 text-amber-800 border-amber-200",
  admin: "bg-blue-100 text-blue-800 border-blue-200",
  member: "bg-gray-100 text-gray-800 border-gray-200",
};

const PERMISSION_LABELS: Record<string, string> = {
  menu_edit: "Menu editing",
  order_manage: "Order management",
};

interface MemberRowProps {
  member: StaffMember;
  myRole: MyRoleResponse | undefined;
  currentUserId: string | undefined;
  allMembers: StaffMember[];
  onUpdateRole: (staffId: number, role: string) => void;
  onUpdatePermissions: (staffId: number, permissions: Record<string, boolean>) => void;
  onRemove: (staffId: number) => void;
  onTransferOwnership: (newOwnerId: string) => void;
}

export function MemberRow({
  member,
  myRole,
  currentUserId,
  allMembers,
  onUpdateRole,
  onUpdatePermissions,
  onRemove,
  onTransferOwnership,
}: MemberRowProps) {
  const [confirmAction, setConfirmAction] = useState<
    | { type: "remove" }
    | { type: "change-role"; newRole: string }
    | { type: "transfer"; newOwnerId: string }
    | null
  >(null);
  const [editPermissionsOpen, setEditPermissionsOpen] = useState(false);
  const [transferDialogOpen, setTransferDialogOpen] = useState(false);
  const [editedPermissions, setEditedPermissions] = useState<Record<string, boolean>>({});
  const [selectedTransferTarget, setSelectedTransferTarget] = useState<string>("");

  const isMe = currentUserId === member.user_id;
  const isOwner = myRole?.role === "owner";
  const isAdmin = myRole?.is_admin ?? false;

  const displayName = [member.first_name, member.last_name].filter(Boolean).join(" ") || member.email;
  const activePermissions = Object.entries(member.permissions).filter(([, v]) => v);

  // Only owners and admins can see the action menu
  // Owners can see their own menu (for transfer), admins cannot act on owners
  const canShowMenu =
    (isOwner && member.role === "owner" && isMe) ||
    (isOwner && member.role !== "owner") ||
    (isAdmin && member.role === "member");

  function handleOpenEditPermissions() {
    setEditedPermissions({ ...member.permissions });
    setEditPermissionsOpen(true);
  }

  function handleSavePermissions() {
    onUpdatePermissions(member.id, editedPermissions);
    setEditPermissionsOpen(false);
  }

  function handleOpenTransferDialog() {
    setSelectedTransferTarget("");
    setTransferDialogOpen(true);
  }

  function handleConfirmTransfer() {
    if (selectedTransferTarget) {
      setTransferDialogOpen(false);
      setConfirmAction({ type: "transfer", newOwnerId: selectedTransferTarget });
    }
  }

  function handleConfirmAction() {
    if (!confirmAction) return;
    switch (confirmAction.type) {
      case "remove":
        onRemove(member.id);
        break;
      case "change-role":
        onUpdateRole(member.id, confirmAction.newRole);
        break;
      case "transfer":
        onTransferOwnership(confirmAction.newOwnerId);
        break;
    }
    setConfirmAction(null);
  }

  const staffForTransfer = allMembers.filter(
    (m) => m.user_id !== currentUserId && (m.role === "admin" || m.role === "member")
  );

  return (
    <>
      <div className="flex items-center justify-between py-3 px-4">
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-muted text-sm font-medium shrink-0">
            {(member.first_name?.[0] || member.email[0]).toUpperCase()}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm font-medium truncate">{displayName}</span>
              <Badge
                variant="outline"
                className={cn("text-xs capitalize", ROLE_BADGE_CLASSES[member.role])}
              >
                {member.role}
              </Badge>
              {isMe && (
                <span className="text-xs text-muted-foreground">(you)</span>
              )}
            </div>
            <p className="text-xs text-muted-foreground truncate">{member.email}</p>
            {member.role === "member" && activePermissions.length > 0 && (
              <div className="flex gap-1.5 mt-1 flex-wrap">
                {activePermissions.map(([key]) => (
                  <span
                    key={key}
                    className="inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800"
                  >
                    {PERMISSION_LABELS[key] || key}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        {canShowMenu && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                <MoreVertical className="h-4 w-4" />
                <span className="sr-only">Actions</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {/* Owner row: only transfer ownership */}
              {member.role === "owner" && isMe && (
                <DropdownMenuItem
                  className="text-destructive focus:text-destructive"
                  onClick={handleOpenTransferDialog}
                >
                  Transfer ownership...
                </DropdownMenuItem>
              )}

              {/* Admin row */}
              {member.role === "admin" && (
                <>
                  <DropdownMenuItem
                    onClick={() =>
                      setConfirmAction({ type: "change-role", newRole: "member" })
                    }
                  >
                    Change to Member
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    className="text-destructive focus:text-destructive"
                    onClick={() => setConfirmAction({ type: "remove" })}
                  >
                    Remove from team
                  </DropdownMenuItem>
                </>
              )}

              {/* Member row */}
              {member.role === "member" && (
                <>
                  <DropdownMenuItem
                    onClick={() =>
                      setConfirmAction({ type: "change-role", newRole: "admin" })
                    }
                  >
                    Change to Admin
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={handleOpenEditPermissions}>
                    Edit permissions
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    className="text-destructive focus:text-destructive"
                    onClick={() => setConfirmAction({ type: "remove" })}
                  >
                    Remove from team
                  </DropdownMenuItem>
                </>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>

      {/* Confirm AlertDialog for remove / role change / transfer */}
      <AlertDialog
        open={confirmAction !== null}
        onOpenChange={(open) => {
          if (!open) setConfirmAction(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {confirmAction?.type === "remove" && "Remove team member"}
              {confirmAction?.type === "change-role" &&
                `Change role to ${confirmAction.newRole}`}
              {confirmAction?.type === "transfer" && "Transfer ownership"}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {confirmAction?.type === "remove" &&
                `Are you sure you want to remove ${displayName} from the team? This action cannot be undone.`}
              {confirmAction?.type === "change-role" &&
                `Are you sure you want to change ${displayName}'s role to ${confirmAction.newRole}?`}
              {confirmAction?.type === "transfer" &&
                "Are you sure you want to transfer ownership? You will be demoted to Admin and this cannot be easily undone."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmAction}
              className={
                confirmAction?.type === "remove" || confirmAction?.type === "transfer"
                  ? "bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  : undefined
              }
            >
              {confirmAction?.type === "remove" && "Remove"}
              {confirmAction?.type === "change-role" && "Change role"}
              {confirmAction?.type === "transfer" && "Transfer ownership"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Transfer ownership dialog - select new owner */}
      <Dialog open={transferDialogOpen} onOpenChange={setTransferDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Transfer ownership</DialogTitle>
            <DialogDescription>
              Select a team member to become the new owner. You will be demoted to Admin.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {staffForTransfer.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">
                No eligible team members to transfer ownership to.
              </p>
            ) : (
              staffForTransfer.map((m) => {
                const name =
                  [m.first_name, m.last_name].filter(Boolean).join(" ") || m.email;
                return (
                  <button
                    key={m.user_id}
                    type="button"
                    className={cn(
                      "w-full flex items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors",
                      selectedTransferTarget === m.user_id
                        ? "bg-primary/10 ring-1 ring-primary"
                        : "hover:bg-muted"
                    )}
                    onClick={() => setSelectedTransferTarget(m.user_id)}
                  >
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-muted text-sm font-medium">
                      {(m.first_name?.[0] || m.email[0]).toUpperCase()}
                    </div>
                    <div>
                      <p className="text-sm font-medium">{name}</p>
                      <p className="text-xs text-muted-foreground">{m.email}</p>
                    </div>
                  </button>
                );
              })
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setTransferDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={!selectedTransferTarget}
              onClick={handleConfirmTransfer}
            >
              Continue
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit permissions dialog */}
      <Dialog open={editPermissionsOpen} onOpenChange={setEditPermissionsOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit permissions</DialogTitle>
            <DialogDescription>
              Choose which permissions {displayName} should have.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            {Object.entries(PERMISSION_LABELS).map(([key, label]) => (
              <div key={key} className="flex items-center space-x-2">
                <Checkbox
                  id={`perm-edit-${key}`}
                  checked={editedPermissions[key] ?? false}
                  onCheckedChange={(checked) =>
                    setEditedPermissions((prev) => ({
                      ...prev,
                      [key]: checked === true,
                    }))
                  }
                />
                <Label htmlFor={`perm-edit-${key}`}>{label}</Label>
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditPermissionsOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSavePermissions}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
