"use client";

import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import { useDismissOnboarding } from "@/hooks/use-onboarding";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";

export function OnboardingBanner() {
  const router = useRouter();
  const { isAuthenticated, user } = useAuthStore();
  const dismissMutation = useDismissOnboarding();

  if (
    !isAuthenticated ||
    !user ||
    user.onboarding_completed ||
    user.onboarding_dismissed
  ) {
    return null;
  }

  const handleDismiss = () => {
    dismissMutation.mutate();
  };

  return (
    <div className="bg-gradient-to-r from-blue-900/50 to-green-900/50 border-b border-blue-800/50 px-4 py-3 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <span className="text-blue-400 text-sm">✨</span>
        <span className="text-sm text-gray-200">
          Complete your profile for a personalized experience
        </span>
        <Button
          variant="default"
          size="sm"
          onClick={() => router.push("/account/onboarding")}
        >
          Set up now
        </Button>
      </div>
      <button
        onClick={handleDismiss}
        className="text-gray-500 hover:text-gray-300 transition-colors"
        aria-label="Dismiss"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
