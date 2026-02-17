"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { useCustomerAuthStore } from "@/stores/customer-auth-store";

interface AppleAuthResponse {
  authorization: { id_token: string };
  user?: { name: { firstName: string; lastName: string } };
}

interface AppleIDAuth {
  auth: {
    init: (config: Record<string, unknown>) => void;
    signIn: () => Promise<AppleAuthResponse>;
  };
}

interface SocialLoginButtonsProps {
  linkOrderId?: string;
  onSuccess?: () => void;
  onError?: (error: string) => void;
  disabled?: boolean;
}

export function SocialLoginButtons({
  linkOrderId,
  onSuccess,
  onError,
  disabled,
}: SocialLoginButtonsProps) {
  const { googleLogin, appleLogin } = useCustomerAuthStore();
  const [loading, setLoading] = useState<"google" | "apple" | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const handleGoogleClick = async () => {
    if (!mounted) return;
    setLoading("google");
    try {
      // Use the Google Identity Services (GIS) library loaded via script tag
      const google = (window as unknown as Record<string, unknown>).google as
        | {
            accounts: {
              oauth2: {
                initTokenClient: (config: Record<string, unknown>) => {
                  requestAccessToken: () => void;
                };
              };
            };
          }
        | undefined;

      if (!google) {
        onError?.("Google Sign-In is not available");
        setLoading(null);
        return;
      }

      const client = google.accounts.oauth2.initTokenClient({
        client_id: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "",
        scope: "email profile",
        callback: async (response: { access_token?: string; error?: string }) => {
          if (response.error || !response.access_token) {
            onError?.("Google login was cancelled or failed");
            setLoading(null);
            return;
          }
          try {
            await googleLogin(response.access_token, linkOrderId);
            onSuccess?.();
          } catch (err) {
            onError?.(err instanceof Error ? err.message : "Google login failed");
          } finally {
            setLoading(null);
          }
        },
      });
      client.requestAccessToken();
    } catch (err) {
      onError?.(err instanceof Error ? err.message : "Google login failed");
      setLoading(null);
    }
  };

  const handleAppleLogin = async () => {
    setLoading("apple");
    try {
      const AppleID = (window as unknown as Record<string, unknown>)
        .AppleID as AppleIDAuth | undefined;
      if (!AppleID) {
        onError?.("Apple Sign-In is not available");
        setLoading(null);
        return;
      }
      const response = await AppleID.auth.signIn();
      const token = response.authorization.id_token;
      const name = response.user
        ? `${response.user.name.firstName} ${response.user.name.lastName}`
        : undefined;
      await appleLogin(token, name, linkOrderId);
      onSuccess?.();
    } catch (err) {
      const errorObj = err as { error?: string };
      if (errorObj?.error !== "popup_closed_by_user") {
        onError?.(err instanceof Error ? err.message : "Apple login failed");
      }
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="space-y-2">
      <Button
        variant="outline"
        className="w-full"
        onClick={handleGoogleClick}
        disabled={disabled || loading !== null || !mounted}
      >
        {loading === "google" ? "Signing in..." : "Continue with Google"}
      </Button>
      <Button
        variant="outline"
        className="w-full"
        onClick={handleAppleLogin}
        disabled={disabled || loading !== null || !mounted}
      >
        {loading === "apple" ? "Signing in..." : "Continue with Apple"}
      </Button>
    </div>
  );
}
