"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuthStore } from "@/stores/auth-store";
import { apiFetch } from "@/lib/api";

interface Restaurant {
  id: string;
  name: string;
  slug: string;
  created_at: string;
}

export default function AdminDashboard() {
  const router = useRouter();
  const { isAuthenticated, logout } = useAuthStore();
  const [restaurants, setRestaurants] = useState<Restaurant[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newSlug, setNewSlug] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isAuthenticated) {
      router.push("/admin/login");
      return;
    }
    apiFetch<{ results: Restaurant[] }>("/api/restaurants/me/")
      .then((data) => {
        setRestaurants(data.results);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [isAuthenticated, router]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const restaurant = await apiFetch<Restaurant>("/api/restaurants/", {
        method: "POST",
        body: JSON.stringify({ name: newName, slug: newSlug }),
      });
      setRestaurants([...restaurants, restaurant]);
      setShowCreate(false);
      setNewName("");
      setNewSlug("");
    } catch {
      // Handle error
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
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
              <Button type="submit">Create</Button>
            </form>
          </Card>
        )}

        <div className="grid gap-4">
          {restaurants.map((r) => (
            <Card key={r.id} className="p-6">
              <div className="flex justify-between items-center">
                <div>
                  <h2 className="text-xl font-semibold">{r.name}</h2>
                  <p className="text-sm text-muted-foreground">/{r.slug}</p>
                </div>
                <div className="flex gap-2">
                  <Link href={`/admin/${r.slug}/menu`}>
                    <Button variant="outline" size="sm">Menu</Button>
                  </Link>
                  <Link href={`/admin/${r.slug}/orders`}>
                    <Button variant="outline" size="sm">Orders</Button>
                  </Link>
                  <Link href={`/admin/${r.slug}/settings`}>
                    <Button variant="outline" size="sm">Settings</Button>
                  </Link>
                  <Link href={`/kitchen/${r.slug}`}>
                    <Button size="sm">Kitchen</Button>
                  </Link>
                </div>
              </div>
            </Card>
          ))}
          {restaurants.length === 0 && (
            <p className="text-center text-muted-foreground py-12">
              No restaurants yet. Create one to get started.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
