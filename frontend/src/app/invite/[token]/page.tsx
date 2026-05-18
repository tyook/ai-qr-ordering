"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  CheckCircle,
  Clock,
  AlertCircle,
  Loader2,
  Check,
  Eye,
  Pencil,
  ClipboardList,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { useAuthStore } from "@/stores/auth-store";
import { useInvitationDetail, useAcceptInvitation } from "@/hooks/use-invitation";
import { useToast } from "@/hooks/use-toast";
import { SocialLoginButtons } from "@/components/SocialLoginButtons";

const PERMISSION_LABELS: Record<string, { label: string; icon: React.ReactNode }> = {
  menu_edit: { label: "Edit menu items", icon: <Pencil className="h-4 w-4" /> },
  order_manage: {
    label: "Manage orders",
    icon: <ClipboardList className="h-4 w-4" />,
  },
};

const BASELINE_PERMISSIONS = [
  { label: "View kitchen dashboard", icon: <Eye className="h-4 w-4" /> },
  { label: "View orders", icon: <Eye className="h-4 w-4" /> },
];

function getRedirectPath(role: string, slug: string) {
  if (role === "admin" || role === "owner") {
    return `/account/restaurants/${slug}/orders`;
  }
  return `/kitchen/${slug}`;
}

export default function InviteAcceptancePage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const token = params.token as string;

  const { isAuthenticated, user, checkAuth, register } = useAuthStore();
  const { data: invitation, isLoading, error } = useInvitationDetail(token);
  const acceptMutation = useAcceptInvitation(token);

  const [regForm, setRegForm] = useState({
    first_name: "",
    last_name: "",
    password: "",
  });
  const [regError, setRegError] = useState("");
  const [isRegistering, setIsRegistering] = useState(false);
  const [socialLoginError, setSocialLoginError] = useState("");

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const handleAccept = async () => {
    try {
      const result = await acceptMutation.mutateAsync(undefined);
      toast({ title: "Invitation accepted!", description: `You have joined ${invitation?.restaurant_name}.` });
      router.push(getRedirectPath(result.role, result.restaurant_slug));
    } catch (err) {
      toast({
        title: "Failed to accept invitation",
        description: err instanceof Error ? err.message : "Something went wrong",
        variant: "destructive",
      });
    }
  };

  const handleRegisterAndAccept = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!invitation) return;

    setRegError("");
    setIsRegistering(true);

    try {
      await register({
        email: invitation.email,
        password: regForm.password,
        first_name: regForm.first_name,
        last_name: regForm.last_name,
      });

      const result = await acceptMutation.mutateAsync(undefined);
      toast({ title: "Account created and invitation accepted!" });
      router.push(getRedirectPath(result.role, result.restaurant_slug));
    } catch (err) {
      setRegError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setIsRegistering(false);
    }
  };

  // Loading state: either auth or invitation is loading
  if (isAuthenticated === null || isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Error fetching invitation (invalid token, revoked, etc.)
  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background px-4">
        <Card className="max-w-md w-full text-center">
          <CardHeader>
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-destructive/10">
              <AlertCircle className="h-7 w-7 text-destructive" />
            </div>
            <CardTitle className="text-xl">Invalid Invitation</CardTitle>
            <CardDescription>
              This invitation link is invalid or has been revoked. Please contact
              the restaurant for a new invitation.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button variant="outline" asChild>
              <Link href="/">Go Home</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!invitation) {
    return null;
  }

  // Expired invitation
  if (invitation.is_expired) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background px-4">
        <Card className="max-w-md w-full text-center">
          <CardHeader>
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-amber-500/10">
              <Clock className="h-7 w-7 text-amber-500" />
            </div>
            <CardTitle className="text-xl">Invitation Expired</CardTitle>
            <CardDescription>
              This invitation has expired. Ask the restaurant to send a new one.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button variant="outline" asChild>
              <Link href="/">Go Home</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Already accepted
  if (invitation.status === "accepted") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background px-4">
        <Card className="max-w-md w-full text-center">
          <CardHeader>
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-green-500/10">
              <CheckCircle className="h-7 w-7 text-green-500" />
            </div>
            <CardTitle className="text-xl">Already Accepted</CardTitle>
            <CardDescription>
              You have already accepted this invitation.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button variant="gradient" asChild>
              <Link
                href={getRedirectPath(invitation.role, invitation.restaurant_slug)}
              >
                Go to Dashboard
              </Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Build permissions list
  const grantedPermissions = Object.entries(invitation.permissions)
    .filter(([, granted]) => granted)
    .map(([key]) => PERMISSION_LABELS[key])
    .filter(Boolean);

  const allPermissions = [
    ...BASELINE_PERMISSIONS,
    ...grantedPermissions,
  ];

  // Invitation header (shared between logged-in and not-logged-in states)
  const invitationHeader = (
    <>
      <div className="mx-auto mb-4 text-5xl">🍽️</div>
      <CardTitle className="text-xl">
        You&apos;ve been invited to join
      </CardTitle>
      <p className="text-2xl font-bold text-primary mt-2">
        {invitation.restaurant_name}
      </p>
      <div className="flex items-center justify-center gap-2 mt-3">
        <span className="text-sm text-muted-foreground">
          Invited by {invitation.invited_by_name}
        </span>
        <Badge variant="secondary" className="capitalize">
          {invitation.role}
        </Badge>
      </div>
    </>
  );

  // Permissions list (shared)
  const permissionsList = (
    <div className="mt-4 space-y-2">
      <p className="text-sm font-medium text-muted-foreground mb-2">
        You will have access to:
      </p>
      {allPermissions.map((perm) => (
        <div key={perm.label} className="flex items-center gap-2 text-sm">
          <div className="flex h-5 w-5 items-center justify-center rounded-full bg-primary/10 text-primary">
            <Check className="h-3 w-3" />
          </div>
          {perm.label}
        </div>
      ))}
    </div>
  );

  // State 1: Valid + logged in
  if (isAuthenticated && user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background px-4">
        <Card className="max-w-md w-full">
          <CardHeader className="text-center">
            {invitationHeader}
          </CardHeader>
          <CardContent className="space-y-4">
            {permissionsList}
            <Button
              variant="gradient"
              size="lg"
              className="w-full mt-6"
              onClick={handleAccept}
              disabled={acceptMutation.isPending}
            >
              {acceptMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Accepting...
                </>
              ) : (
                "Accept Invitation"
              )}
            </Button>
            <p className="text-xs text-center text-muted-foreground">
              Logged in as {user.email}
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  // State 2 & 3: Not logged in - show registration form + login link
  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <Card className="max-w-md w-full">
        <CardHeader className="text-center">
          {invitationHeader}
        </CardHeader>
        <CardContent className="space-y-4">
          {permissionsList}

          <Separator className="my-4" />

          <form onSubmit={handleRegisterAndAccept} className="space-y-4">
            <p className="text-sm font-medium">Create an account to join</p>
            <div>
              <Label htmlFor="invite-email">Email</Label>
              <Input
                id="invite-email"
                type="email"
                value={invitation.email}
                disabled
                className="bg-muted"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="invite-first-name">First name</Label>
                <Input
                  id="invite-first-name"
                  value={regForm.first_name}
                  onChange={(e) =>
                    setRegForm({ ...regForm, first_name: e.target.value })
                  }
                  required
                />
              </div>
              <div>
                <Label htmlFor="invite-last-name">Last name</Label>
                <Input
                  id="invite-last-name"
                  value={regForm.last_name}
                  onChange={(e) =>
                    setRegForm({ ...regForm, last_name: e.target.value })
                  }
                  required
                />
              </div>
            </div>
            <div>
              <Label htmlFor="invite-password">Password</Label>
              <Input
                id="invite-password"
                type="password"
                value={regForm.password}
                onChange={(e) =>
                  setRegForm({ ...regForm, password: e.target.value })
                }
                required
                minLength={8}
              />
            </div>
            {regError && <p className="text-destructive text-sm">{regError}</p>}
            <Button
              type="submit"
              variant="gradient"
              size="lg"
              className="w-full"
              disabled={isRegistering}
            >
              {isRegistering ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Creating account...
                </>
              ) : (
                "Create Account & Join"
              )}
            </Button>
          </form>

          <div className="relative my-2">
            <div className="absolute inset-0 flex items-center">
              <Separator className="w-full" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-card px-2 text-muted-foreground">or</span>
            </div>
          </div>

          <SocialLoginButtons
            onSuccess={handleAccept}
            onError={(err) => setSocialLoginError(err)}
            disabled={isRegistering}
          />
          {socialLoginError && <p className="text-destructive text-sm text-center">{socialLoginError}</p>}

          <p className="text-sm text-center text-muted-foreground">
            Already have an account?{" "}
            <Link
              href={`/account/login?returnUrl=/invite/${token}`}
              className="text-primary hover:underline font-medium"
            >
              Log in
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
