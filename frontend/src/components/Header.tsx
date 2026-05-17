"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  CreditCard,
  ClipboardList,
  LogOut,
  Menu,
  ShoppingBag,
  Store,
  UtensilsCrossed,
  User as UserIcon,
  X,
} from "lucide-react";
import { useAuthStore } from "@/stores/auth-store";
import { useTheme } from "@/components/ThemeProvider";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export function Header() {
  const router = useRouter();
  const { isAuthenticated, user, logout } = useAuthStore();
  const { theme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const handleLogout = async () => {
    await logout();
    router.push("/");
  };

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const isAdmin = theme === "admin";

  return (
    <header className={`sticky top-0 z-50 w-full border-b ${isAdmin ? "border-border bg-card shadow-sm" : "border-border bg-background/80 backdrop-blur-xl"}`}>
      <div className="container mx-auto flex h-14 items-center px-4">
        {/* Logo */}
        <Link href="/" className="mr-6 flex items-center gap-2 font-bold">
          <UtensilsCrossed className="h-5 w-5 text-primary" />
          <span className={isAdmin ? "text-foreground" : "gradient-text"}>MenuChat</span>
        </Link>

        {/* Desktop Navigation */}
        <nav className="hidden items-center gap-1 text-sm md:flex">
          {mounted && isAuthenticated && (
            <>
              {user?.is_restaurant_owner && (
                <Link href="/account/restaurants">
                  <Button variant="ghost" size="sm" className="gap-1.5">
                    <Store className="h-4 w-4" />
                    My Restaurants
                  </Button>
                </Link>
              )}
              <Link href="/account/profile">
                <Button variant="ghost" size="sm" className="gap-1.5">
                  <UserIcon className="h-4 w-4" />
                  Profile
                </Button>
              </Link>
              <Link href="/account/orders">
                <Button variant="ghost" size="sm" className="gap-1.5">
                  <ShoppingBag className="h-4 w-4" />
                  Orders
                </Button>
              </Link>
            </>
          )}
        </nav>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Auth section — render after mount to avoid hydration mismatch from localStorage */}
        {!mounted ? (
          <div className="h-9 w-9" />
        ) : (
          <div className="flex items-center gap-1">
            {/* Mobile hamburger menu — always visible on mobile */}
            <div className="md:hidden">
              <DropdownMenu modal={false} open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" className="rounded-full">
                    {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
                    <span className="sr-only">Menu</span>
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-48">
                  {isAuthenticated ? (
                    <>
                      {user?.is_restaurant_owner && (
                        <DropdownMenuItem onClick={() => router.push("/account/restaurants")}>
                          <Store className="mr-2 h-4 w-4" />
                          My Restaurants
                        </DropdownMenuItem>
                      )}
                      <DropdownMenuItem onClick={() => router.push("/account/profile")}>
                        <UserIcon className="mr-2 h-4 w-4" />
                        Profile
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => router.push("/account/orders")}>
                        <ShoppingBag className="mr-2 h-4 w-4" />
                        Orders
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem
                        onClick={() => router.push("/account/payment-methods")}
                      >
                        <CreditCard className="mr-2 h-4 w-4" />
                        Payment Methods
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onClick={handleLogout}>
                        <LogOut className="mr-2 h-4 w-4" />
                        Log out
                      </DropdownMenuItem>
                    </>
                  ) : (
                    <DropdownMenuItem onClick={() => router.push("/account/login")}>
                      <UserIcon className="mr-2 h-4 w-4" />
                      Log in
                    </DropdownMenuItem>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
            </div>

            {/* Desktop: user dropdown (authenticated) or login button (unauthenticated) */}
            {isAuthenticated ? (
              <div className="hidden md:block">
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon" className="rounded-full">
                      <UserIcon className="h-5 w-5" />
                      <span className="sr-only">User menu</span>
                    </Button>
                  </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-48">
                  {user && (
                    <>
                      <DropdownMenuLabel className="font-normal">
                        <div className="flex flex-col gap-1">
                          <p className="text-sm font-medium">{user.name}</p>
                          <p className="text-xs text-muted-foreground">
                            {user.email}
                          </p>
                        </div>
                      </DropdownMenuLabel>
                      <DropdownMenuSeparator />
                    </>
                  )}
                  {user?.onboarding_completed === false && (
                    <>
                      <DropdownMenuItem
                        onClick={() => router.push("/account/onboarding")}
                      >
                        <ClipboardList className="mr-2 h-4 w-4" />
                        Complete your profile
                      </DropdownMenuItem>
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
                  <DropdownMenuItem
                    onClick={() => router.push("/account/payment-methods")}
                  >
                    <CreditCard className="mr-2 h-4 w-4" />
                    Payment Methods
                  </DropdownMenuItem>
                  {user?.is_restaurant_owner && (
                    <DropdownMenuItem
                      onClick={() => router.push("/account/restaurants")}
                    >
                      <Store className="mr-2 h-4 w-4" />
                      My Restaurants
                    </DropdownMenuItem>
                  )}
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={handleLogout}>
                    <LogOut className="mr-2 h-4 w-4" />
                    Log out
                  </DropdownMenuItem>
                </DropdownMenuContent>
                </DropdownMenu>
              </div>
            ) : (
              <Link href="/account/login" className="hidden md:inline-flex">
                <Button size="sm" variant="gradient">Log in</Button>
              </Link>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
