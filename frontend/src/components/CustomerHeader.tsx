"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { LogOut, ShoppingBag, UtensilsCrossed, User as UserIcon } from "lucide-react";
import { useCustomerAuthStore } from "@/stores/customer-auth-store";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export function CustomerHeader() {
  const router = useRouter();
  const { isAuthenticated, customer, logout } = useCustomerAuthStore();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const handleLogout = () => {
    logout();
    router.push("/");
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto flex h-14 items-center px-4">
        {/* Logo */}
        <Link href="/" className="mr-6 flex items-center gap-2 font-bold">
          <UtensilsCrossed className="h-5 w-5" />
          <span>QR Order</span>
        </Link>

        {/* Navigation */}
        <nav className="flex items-center gap-1 text-sm">
          <Link href="/account/orders">
            <Button variant="ghost" size="sm" className="gap-1.5">
              <ShoppingBag className="h-4 w-4" />
              Orders
            </Button>
          </Link>
          <Link href="/account/profile">
            <Button variant="ghost" size="sm" className="gap-1.5">
              <UserIcon className="h-4 w-4" />
              Profile
            </Button>
          </Link>
        </nav>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Auth section — render after mount to avoid hydration mismatch from localStorage */}
        {!mounted ? (
          <div className="h-9 w-9" />
        ) : isAuthenticated ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="rounded-full">
                <UserIcon className="h-5 w-5" />
                <span className="sr-only">User menu</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              {customer && (
                <>
                  <DropdownMenuLabel className="font-normal">
                    <div className="flex flex-col gap-1">
                      <p className="text-sm font-medium">{customer.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {customer.email}
                      </p>
                    </div>
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator />
                </>
              )}
              <DropdownMenuItem onClick={() => router.push("/account/orders")}>
                <ShoppingBag className="mr-2 h-4 w-4" />
                Orders
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => router.push("/account/profile")}>
                <UserIcon className="mr-2 h-4 w-4" />
                Profile
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={handleLogout}>
                <LogOut className="mr-2 h-4 w-4" />
                Log out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        ) : (
          <Link href="/account/login">
            <Button size="sm">Log in</Button>
          </Link>
        )}
      </div>
    </header>
  );
}
