"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useAuthStore } from "@/stores/auth-store";
import { useRequireRestaurantAccess } from "@/hooks/use-auth";
import { useMyRestaurants } from "@/hooks/use-my-restaurants";
import { useCan } from "@/hooks/use-my-role";
import { RestaurantDetailsStep } from "@/components/onboarding/restaurant-details-step";
import type { Restaurant } from "@/types";

function RestaurantCard({ r }: { r: Restaurant }) {
  const can = useCan(r.slug);
  const isAdmin = can("is_admin");
  const canEditMenu = can("menu_edit");

  return (
    <Card className="bg-card border border-border rounded-2xl p-5 hover:border-primary/30 transition-colors">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-xl font-semibold text-foreground">{r.name}</h2>
          <p className="text-sm text-muted-foreground">/{r.slug}</p>
          {r.subscription && (
            <div className="flex items-center gap-2 mt-1">
              <span className="text-xs px-2 py-0.5 rounded-full bg-muted">
                {r.subscription.plan_name}
              </span>
              <span className={`text-xs px-2 py-0.5 rounded-full ${
                r.subscription.is_active ? "bg-success/10 text-success" : "bg-destructive/10 text-destructive"
              }`}>
                {r.subscription.status.replace("_", " ")}
              </span>
            </div>
          )}
        </div>
        <div className="flex gap-2 flex-wrap">
          {canEditMenu && (
            <Link href={`/account/restaurants/${r.slug}/menu`}>
              <Button variant="outline" size="sm">Menu</Button>
            </Link>
          )}
          <Link href={`/account/restaurants/${r.slug}/orders`}>
            <Button variant="outline" size="sm">Orders</Button>
          </Link>
          {isAdmin && (
            <>
              <Link href={`/account/restaurants/${r.slug}/analytics`}>
                <Button variant="outline" size="sm">Analytics</Button>
              </Link>
              <Link href={`/account/restaurants/${r.slug}/billing`}>
                <Button variant="outline" size="sm">Billing</Button>
              </Link>
              <Link href={`/account/restaurants/${r.slug}/settings`}>
                <Button variant="outline" size="sm">Settings</Button>
              </Link>
              <Link href={`/account/restaurants/${r.slug}/team`}>
                <Button variant="outline" size="sm">Team</Button>
              </Link>
            </>
          )}
          {r.payment_model === "tab" && (
            <Link href={`/account/restaurants/${r.slug}/hall-status`}>
              <Button variant="outline" size="sm">Hall Status</Button>
            </Link>
          )}
          <Link href={`/kitchen/${r.slug}`}>
            <Button size="sm">Kitchen</Button>
          </Link>
        </div>
      </div>
    </Card>
  );
}

export default function RestaurantsDashboard() {
  const isAuthenticated = useRequireRestaurantAccess();
  const { logout } = useAuthStore();
  const [showCreate, setShowCreate] = useState(false);

  const { data: restaurants, isLoading } = useMyRestaurants(isAuthenticated === true);

  if (isAuthenticated === null || isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (isAuthenticated === false) {
    return null;
  }

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-4xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-2xl font-bold">My Restaurants</h1>
          <div className="flex gap-2">
            <Button variant="gradient" onClick={() => setShowCreate(!showCreate)}>
              + New Restaurant
            </Button>
            <Button variant="outline" onClick={logout}>
              Sign Out
            </Button>
          </div>
        </div>

        {showCreate && (
          <Card className="bg-card border border-border rounded-2xl p-6 mb-6">
            <RestaurantDetailsStep
              onCreated={() => setShowCreate(false)}
              onBack={() => setShowCreate(false)}
            />
          </Card>
        )}

        <div className="grid gap-4">
          {restaurants?.map((r) => (
            <RestaurantCard key={r.id} r={r} />
          ))}
          {(!restaurants || restaurants.length === 0) && (
            <p className="text-center text-muted-foreground py-12">
              No restaurants yet. Create one to get started.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
