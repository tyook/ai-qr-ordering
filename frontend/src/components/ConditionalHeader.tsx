"use client";

import { usePathname } from "next/navigation";
import { Header } from "@/components/Header";
import { CustomerHeader } from "@/components/CustomerHeader";

export function ConditionalHeader() {
  const pathname = usePathname();

  // Don't show any header on /order/* routes
  if (pathname.startsWith("/order/")) {
    return null;
  }

  // Show CustomerHeader on /account/* routes
  if (pathname.startsWith("/account/")) {
    return <CustomerHeader />;
  }

  // Show admin Header on /admin/* and /kitchen/* routes (and others by default)
  return <Header />;
}
