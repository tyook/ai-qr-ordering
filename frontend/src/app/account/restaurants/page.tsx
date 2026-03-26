"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useAuthStore } from "@/stores/auth-store";
import { useRequireRestaurantAccess } from "@/hooks/use-auth";
import { useMyRestaurants } from "@/hooks/use-my-restaurants";
import { useCreateRestaurant } from "@/hooks/use-create-restaurant";

export default function RestaurantsDashboard() {
  const isAuthenticated = useRequireRestaurantAccess();
  const { logout } = useAuthStore();
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newSlug, setNewSlug] = useState("");
  const [newPhone, setNewPhone] = useState("");
  const [newAddress, setNewAddress] = useState("");
  const [newHomepage, setNewHomepage] = useState("");
  const [newLogoUrl, setNewLogoUrl] = useState("");

  const { data: restaurants, isLoading } = useMyRestaurants(isAuthenticated === true);
  const createRestaurant = useCreateRestaurant();

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    createRestaurant.mutate(
      {
        name: newName,
        slug: newSlug,
        phone: newPhone || undefined,
        address: newAddress || undefined,
        homepage: newHomepage || undefined,
        logo_url: newLogoUrl || undefined,
      },
      {
        onSuccess: () => {
          setShowCreate(false);
          setNewName("");
          setNewSlug("");
          setNewPhone("");
          setNewAddress("");
          setNewHomepage("");
          setNewLogoUrl("");
        },
      }
    );
  };

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
            <Button onClick={() => setShowCreate(!showCreate)}>
              + New Restaurant
            </Button>
            <Button variant="outline" onClick={logout}>
              Sign Out
            </Button>
          </div>
        </div>

        {showCreate && (
          <Card className="p-6 mb-6">
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <Label>Restaurant Name</Label>
                <Input
                  value={newName}
                  onChange={(e) => {
                    setNewName(e.target.value);
                    setNewSlug(
                      e.target.value
                        .toLowerCase()
                        .replace(/[^a-z0-9]+/g, "-")
                        .replace(/^-|-$/g, "")
                    );
                  }}
                  placeholder="My Pizza Place"
                  required
                />
              </div>
              <div>
                <Label>URL Slug</Label>
                <Input
                  value={newSlug}
                  onChange={(e) => setNewSlug(e.target.value)}
                  placeholder="my-pizza-place"
                  required
                />
              </div>
              <div>
                <Label>Phone Number <span className="text-muted-foreground text-xs">(optional)</span></Label>
                <Input
                  value={newPhone}
                  onChange={(e) => setNewPhone(e.target.value)}
                  placeholder="(555) 123-4567"
                />
              </div>
              <div>
                <Label>Address <span className="text-muted-foreground text-xs">(optional)</span></Label>
                <Textarea
                  value={newAddress}
                  onChange={(e) => setNewAddress(e.target.value)}
                  placeholder="123 Main St, City, State 12345"
                  rows={2}
                />
              </div>
              <div>
                <Label>Homepage URL <span className="text-muted-foreground text-xs">(optional)</span></Label>
                <Input
                  value={newHomepage}
                  onChange={(e) => setNewHomepage(e.target.value)}
                  placeholder="https://www.mypizzaplace.com"
                  type="url"
                />
              </div>
              <div>
                <Label>Logo URL <span className="text-muted-foreground text-xs">(optional)</span></Label>
                <Input
                  value={newLogoUrl}
                  onChange={(e) => setNewLogoUrl(e.target.value)}
                  placeholder="https://example.com/logo.png"
                  type="url"
                />
              </div>
              <Button type="submit" disabled={createRestaurant.isPending}>
                {createRestaurant.isPending ? "Creating..." : "Create"}
              </Button>
            </form>
          </Card>
        )}

        <div className="grid gap-4">
          {restaurants?.map((r) => (
            <Card key={r.id} className="p-6">
              <div className="flex justify-between items-center">
                <div>
                  <h2 className="text-xl font-semibold">{r.name}</h2>
                  <p className="text-sm text-muted-foreground">/{r.slug}</p>
                  {r.subscription && (
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-xs px-2 py-0.5 rounded-full bg-muted">
                        {r.subscription.plan_name}
                      </span>
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        r.subscription.is_active ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"
                      }`}>
                        {r.subscription.status.replace("_", " ")}
                      </span>
                    </div>
                  )}
                </div>
                <div className="flex gap-2">
                  <Link href={`/account/restaurants/${r.slug}/menu`}>
                    <Button variant="outline" size="sm">Menu</Button>
                  </Link>
                  <Link href={`/account/restaurants/${r.slug}/orders`}>
                    <Button variant="outline" size="sm">Orders</Button>
                  </Link>
                  <Link href={`/account/restaurants/${r.slug}/billing`}>
                    <Button variant="outline" size="sm">Billing</Button>
                  </Link>
                  <Link href={`/account/restaurants/${r.slug}/settings`}>
                    <Button variant="outline" size="sm">Settings</Button>
                  </Link>
                  <Link href={`/kitchen/${r.slug}`}>
                    <Button size="sm">Kitchen</Button>
                  </Link>
                </div>
              </div>
            </Card>
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
