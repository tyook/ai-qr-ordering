"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

const PERMISSION_OPTIONS = [
  { key: "menu_edit", label: "Menu editing" },
  { key: "order_manage", label: "Order management" },
];

interface InviteModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onInvite: (data: {
    email: string;
    role: string;
    permissions?: Record<string, boolean>;
  }) => void;
  isLoading?: boolean;
}

export function InviteModal({
  open,
  onOpenChange,
  onInvite,
  isLoading,
}: InviteModalProps) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"admin" | "member">("member");
  const [permissions, setPermissions] = useState<Record<string, boolean>>({
    menu_edit: false,
    order_manage: false,
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim()) return;

    onInvite({
      email: email.trim(),
      role,
      permissions: role === "member" ? permissions : undefined,
    });
  }

  function resetForm() {
    setEmail("");
    setRole("member");
    setPermissions({ menu_edit: false, order_manage: false });
  }

  function handleOpenChange(open: boolean) {
    if (!open) resetForm();
    onOpenChange(open);
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Invite team member</DialogTitle>
          <DialogDescription>
            Send an invitation to join your restaurant team.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="invite-email">Email address</Label>
            <Input
              id="invite-email"
              type="email"
              placeholder="colleague@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div className="space-y-2">
            <Label>Role</Label>
            <div className="flex gap-1 bg-muted rounded-lg p-1">
              <button
                type="button"
                className={cn(
                  "flex-1 px-3 py-1.5 text-sm rounded-md transition-colors",
                  role === "admin"
                    ? "bg-background text-foreground font-medium shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                )}
                onClick={() => setRole("admin")}
              >
                Admin
              </button>
              <button
                type="button"
                className={cn(
                  "flex-1 px-3 py-1.5 text-sm rounded-md transition-colors",
                  role === "member"
                    ? "bg-background text-foreground font-medium shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                )}
                onClick={() => setRole("member")}
              >
                Member
              </button>
            </div>
            <p className="text-xs text-muted-foreground">
              {role === "admin"
                ? "Admins have full access to manage the restaurant."
                : "Members have limited access based on assigned permissions."}
            </p>
          </div>

          {role === "member" && (
            <div className="space-y-3">
              <Label>Permissions</Label>
              {PERMISSION_OPTIONS.map((perm) => (
                <div key={perm.key} className="flex items-center space-x-2">
                  <Checkbox
                    id={`invite-perm-${perm.key}`}
                    checked={permissions[perm.key] ?? false}
                    onCheckedChange={(checked) =>
                      setPermissions((prev) => ({
                        ...prev,
                        [perm.key]: checked === true,
                      }))
                    }
                  />
                  <Label htmlFor={`invite-perm-${perm.key}`}>{perm.label}</Label>
                </div>
              ))}
            </div>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => handleOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isLoading || !email.trim()}>
              {isLoading ? "Sending..." : "Send invite"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
