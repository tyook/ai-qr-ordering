"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";

export function useRequireAuth() {
  const { isAuthenticated, checkAuth } = useAuthStore();
  const router = useRouter();

  useEffect(() => {
    if (isAuthenticated === null) {
      checkAuth().then((ok) => {
        if (!ok) router.push("/account/login");
      });
    } else if (isAuthenticated === false) {
      router.push("/account/login");
    }
  }, [isAuthenticated, checkAuth, router]);

  return isAuthenticated;
}

export function useRequireRestaurantAccess() {
  const auth = useRequireAuth();
  const { user } = useAuthStore();
  const router = useRouter();

  useEffect(() => {
    if (auth === true && user && !user.is_restaurant_owner) {
      router.push("/account/profile");
    }
  }, [auth, user, router]);

  return auth;
}
