# Phase 6: Frontend - Kitchen Dashboard & Admin Panel

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the real-time kitchen dashboard (WebSocket-powered order board) and the admin panel (auth, menu management, QR code generation).

**Architecture:** Kitchen dashboard at `/kitchen/[slug]/` uses native WebSocket to listen for order updates, displays orders in Kanban-style columns. Admin panel at `/admin/` uses JWT auth with token stored in localStorage. Menu management provides CRUD for categories, items, variants, modifiers.

**Tech Stack:** Next.js 14, TypeScript, Tailwind CSS, shadcn/ui, Zustand, qrcode.react, WebSocket API

**Depends on:** Phase 0 (frontend scaffolding), Phase 4 (backend WebSocket + kitchen API), Phase 5 (types/API client)

---

## Task 1: WebSocket Hook

**Files:**
- Create: `frontend/src/hooks/use-websocket.ts`

**Step 1: Create the hook**

Create `frontend/src/hooks/use-websocket.ts`:

```typescript
"use client";

import { useEffect, useRef, useCallback, useState } from "react";

interface UseWebSocketOptions {
  url: string;
  onMessage: (data: unknown) => void;
  reconnectInterval?: number;
}

export function useWebSocket({
  url,
  onMessage,
  reconnectInterval = 3000,
}: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(url);

    ws.onopen = () => {
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch {
        // Ignore non-JSON messages
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      reconnectTimeoutRef.current = setTimeout(connect, reconnectInterval);
    };

    ws.onerror = () => {
      ws.close();
    };

    wsRef.current = ws;
  }, [url, onMessage, reconnectInterval]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      wsRef.current?.close();
    };
  }, [connect]);

  return { isConnected };
}
```

**Step 2: Commit**

```bash
git add frontend/src/hooks/
git commit -m "feat: add WebSocket hook with auto-reconnect"
```

---

## Task 2: Kitchen Dashboard Store

**Files:**
- Create: `frontend/src/stores/kitchen-store.ts`

**Step 1: Create the store**

Create `frontend/src/stores/kitchen-store.ts`:

```typescript
import { create } from "zustand";
import type { OrderResponse } from "@/types";

interface KitchenState {
  orders: OrderResponse[];
  addOrUpdateOrder: (order: OrderResponse) => void;
  getOrdersByStatus: (status: string) => OrderResponse[];
}

export const useKitchenStore = create<KitchenState>((set, get) => ({
  orders: [],

  addOrUpdateOrder: (order) =>
    set((state) => {
      const existing = state.orders.findIndex((o) => o.id === order.id);
      if (existing >= 0) {
        const updated = [...state.orders];
        updated[existing] = order;
        return { orders: updated };
      }
      return { orders: [order, ...state.orders] };
    }),

  getOrdersByStatus: (status) => {
    return get().orders.filter((o) => o.status === status);
  },
}));
```

**Step 2: Commit**

```bash
git add frontend/src/stores/
git commit -m "feat: add kitchen Zustand store"
```

---

## Task 3: Kitchen Dashboard Page

**Files:**
- Create: `frontend/src/app/kitchen/[slug]/page.tsx`
- Create: `frontend/src/app/kitchen/[slug]/components/OrderCard.tsx`
- Create: `frontend/src/app/kitchen/[slug]/components/OrderColumn.tsx`

**Step 1: Create component directory**

```bash
mkdir -p frontend/src/app/kitchen/\[slug\]/components
```

**Step 2: Create OrderCard component**

Create `frontend/src/app/kitchen/[slug]/components/OrderCard.tsx`:

```tsx
"use client";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { OrderResponse } from "@/types";

interface OrderCardProps {
  order: OrderResponse;
  onAdvance: (orderId: string) => void;
}

function timeSince(dateString: string): string {
  const seconds = Math.floor(
    (Date.now() - new Date(dateString).getTime()) / 1000
  );
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}

const statusLabels: Record<string, string> = {
  confirmed: "Start Preparing",
  preparing: "Mark Ready",
  ready: "Complete",
};

export function OrderCard({ order, onAdvance }: OrderCardProps) {
  return (
    <Card
      className="p-4 cursor-pointer hover:shadow-md transition-shadow"
      onClick={() => onAdvance(order.id)}
    >
      <div className="flex justify-between items-start mb-2">
        <div>
          <span className="font-bold text-sm">
            #{order.id.slice(0, 8)}
          </span>
          {order.table_identifier && (
            <Badge variant="outline" className="ml-2">
              Table {order.table_identifier}
            </Badge>
          )}
        </div>
        <span className="text-xs text-muted-foreground">
          {timeSince(order.created_at)}
        </span>
      </div>

      <ul className="text-sm space-y-1 mb-3">
        {order.items.map((item) => (
          <li key={item.id}>
            {item.quantity}x {item.name} ({item.variant_label})
            {item.special_requests && (
              <span className="text-muted-foreground italic">
                {" "}
                - {item.special_requests}
              </span>
            )}
          </li>
        ))}
      </ul>

      <div className="text-xs text-center text-primary font-medium">
        Tap to {statusLabels[order.status] || "update"}
      </div>
    </Card>
  );
}
```

**Step 3: Create OrderColumn component**

Create `frontend/src/app/kitchen/[slug]/components/OrderColumn.tsx`:

```tsx
"use client";

import { Badge } from "@/components/ui/badge";
import { OrderCard } from "./OrderCard";
import type { OrderResponse } from "@/types";

interface OrderColumnProps {
  title: string;
  orders: OrderResponse[];
  onAdvance: (orderId: string) => void;
  variant: "default" | "secondary" | "destructive" | "outline";
}

export function OrderColumn({
  title,
  orders,
  onAdvance,
  variant,
}: OrderColumnProps) {
  return (
    <div className="flex-1 min-w-[280px]">
      <div className="flex items-center gap-2 mb-4">
        <h2 className="font-semibold text-lg">{title}</h2>
        <Badge variant={variant}>{orders.length}</Badge>
      </div>
      <div className="space-y-3">
        {orders.map((order) => (
          <OrderCard key={order.id} order={order} onAdvance={onAdvance} />
        ))}
        {orders.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-8">
            No orders
          </p>
        )}
      </div>
    </div>
  );
}
```

**Step 4: Create the kitchen page**

Create `frontend/src/app/kitchen/[slug]/page.tsx`:

```tsx
"use client";

import { useCallback } from "react";
import { useParams } from "next/navigation";
import { useKitchenStore } from "@/stores/kitchen-store";
import { useWebSocket } from "@/hooks/use-websocket";
import { OrderColumn } from "./components/OrderColumn";
import { Badge } from "@/components/ui/badge";
import type { OrderResponse } from "@/types";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

const NEXT_STATUS: Record<string, string> = {
  confirmed: "preparing",
  preparing: "ready",
  ready: "completed",
};

export default function KitchenPage() {
  const params = useParams<{ slug: string }>();
  const slug = params.slug;
  const { orders, addOrUpdateOrder } = useKitchenStore();

  const handleMessage = useCallback(
    (data: unknown) => {
      addOrUpdateOrder(data as OrderResponse);
    },
    [addOrUpdateOrder]
  );

  const { isConnected } = useWebSocket({
    url: `${WS_URL}/ws/kitchen/${slug}/`,
    onMessage: handleMessage,
  });

  const handleAdvance = async (orderId: string) => {
    const order = orders.find((o) => o.id === orderId);
    if (!order) return;

    const nextStatus = NEXT_STATUS[order.status];
    if (!nextStatus) return;

    const token = localStorage.getItem("access_token");
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/kitchen/orders/${orderId}/`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ status: nextStatus }),
        }
      );
      if (response.ok) {
        const updated = await response.json();
        addOrUpdateOrder(updated);
      }
    } catch {
      // Handle error silently for now
    }
  };

  const confirmed = orders.filter((o) => o.status === "confirmed");
  const preparing = orders.filter((o) => o.status === "preparing");
  const ready = orders.filter((o) => o.status === "ready");

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Kitchen Dashboard</h1>
        <Badge variant={isConnected ? "default" : "destructive"}>
          {isConnected ? "Connected" : "Disconnected"}
        </Badge>
      </div>

      <div className="flex gap-6 overflow-x-auto">
        <OrderColumn
          title="New Orders"
          orders={confirmed}
          onAdvance={handleAdvance}
          variant="destructive"
        />
        <OrderColumn
          title="Preparing"
          orders={preparing}
          onAdvance={handleAdvance}
          variant="secondary"
        />
        <OrderColumn
          title="Ready"
          orders={ready}
          onAdvance={handleAdvance}
          variant="default"
        />
      </div>
    </div>
  );
}
```

**Step 5: Verify build**

```bash
cd frontend
npm run build
```

Expected: Build succeeds.

**Step 6: Commit**

```bash
git add frontend/src/
git commit -m "feat: add real-time kitchen dashboard with WebSocket and Kanban columns"
```

---

## Task 4: Auth Store & Login/Register Pages

**Files:**
- Create: `frontend/src/stores/auth-store.ts`
- Create: `frontend/src/app/admin/login/page.tsx`
- Create: `frontend/src/app/admin/register/page.tsx`

**Step 1: Create auth store**

Create `frontend/src/stores/auth-store.ts`:

```typescript
import { create } from "zustand";
import { apiFetch } from "@/lib/api";

interface AuthState {
  isAuthenticated: boolean;
  user: { id: string; email: string; first_name: string; last_name: string } | null;
  login: (email: string, password: string) => Promise<void>;
  register: (data: {
    email: string;
    password: string;
    first_name: string;
    last_name: string;
  }) => Promise<void>;
  logout: () => void;
  checkAuth: () => boolean;
}

export const useAuthStore = create<AuthState>((set) => ({
  isAuthenticated:
    typeof window !== "undefined" && !!localStorage.getItem("access_token"),
  user: null,

  login: async (email, password) => {
    const data = await apiFetch<{ access: string; refresh: string }>(
      "/api/auth/login/",
      {
        method: "POST",
        body: JSON.stringify({ email, password }),
      }
    );
    localStorage.setItem("access_token", data.access);
    localStorage.setItem("refresh_token", data.refresh);
    set({ isAuthenticated: true });
  },

  register: async (formData) => {
    const data = await apiFetch<{
      access: string;
      refresh: string;
      user: { id: string; email: string; first_name: string; last_name: string };
    }>("/api/auth/register/", {
      method: "POST",
      body: JSON.stringify(formData),
    });
    localStorage.setItem("access_token", data.access);
    localStorage.setItem("refresh_token", data.refresh);
    set({ isAuthenticated: true, user: data.user });
  },

  logout: () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    set({ isAuthenticated: false, user: null });
  },

  checkAuth: () => {
    return !!localStorage.getItem("access_token");
  },
}));
```

**Step 2: Create login page**

Create `frontend/src/app/admin/login/page.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { useAuthStore } from "@/stores/auth-store";

export default function LoginPage() {
  const router = useRouter();
  const login = useAuthStore((s) => s.login);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      router.push("/admin");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <Card className="w-full max-w-md p-8">
        <h1 className="text-2xl font-bold mb-6 text-center">Sign In</h1>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div>
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {error && <p className="text-destructive text-sm">{error}</p>}
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "Signing in..." : "Sign In"}
          </Button>
        </form>
        <p className="text-sm text-center mt-4 text-muted-foreground">
          Don&apos;t have an account?{" "}
          <Link href="/admin/register" className="text-primary underline">
            Register
          </Link>
        </p>
      </Card>
    </div>
  );
}
```

**Step 3: Create register page**

Create `frontend/src/app/admin/register/page.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { useAuthStore } from "@/stores/auth-store";

export default function RegisterPage() {
  const router = useRouter();
  const register = useAuthStore((s) => s.register);
  const [form, setForm] = useState({
    email: "",
    password: "",
    first_name: "",
    last_name: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await register(form);
      router.push("/admin");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <Card className="w-full max-w-md p-8">
        <h1 className="text-2xl font-bold mb-6 text-center">Create Account</h1>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="first_name">First Name</Label>
              <Input
                id="first_name"
                value={form.first_name}
                onChange={(e) => setForm({ ...form, first_name: e.target.value })}
                required
              />
            </div>
            <div>
              <Label htmlFor="last_name">Last Name</Label>
              <Input
                id="last_name"
                value={form.last_name}
                onChange={(e) => setForm({ ...form, last_name: e.target.value })}
                required
              />
            </div>
          </div>
          <div>
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              required
            />
          </div>
          <div>
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              required
            />
          </div>
          {error && <p className="text-destructive text-sm">{error}</p>}
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "Creating account..." : "Create Account"}
          </Button>
        </form>
        <p className="text-sm text-center mt-4 text-muted-foreground">
          Already have an account?{" "}
          <Link href="/admin/login" className="text-primary underline">
            Sign in
          </Link>
        </p>
      </Card>
    </div>
  );
}
```

**Step 4: Commit**

```bash
git add frontend/src/
git commit -m "feat: add auth store, login, and register pages"
```

---

## Task 5: Admin Dashboard & Restaurant List

**Files:**
- Create: `frontend/src/app/admin/page.tsx`

**Step 1: Create admin dashboard page**

Create `frontend/src/app/admin/page.tsx`:

```tsx
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
```

**Step 2: Commit**

```bash
git add frontend/src/
git commit -m "feat: add admin dashboard with restaurant list and creation"
```

---

## Task 6: Menu Management Page

**Files:**
- Create: `frontend/src/app/admin/[slug]/menu/page.tsx`

**Step 1: Create menu management page**

Create `frontend/src/app/admin/[slug]/menu/page.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { useAuthStore } from "@/stores/auth-store";
import { apiFetch } from "@/lib/api";

interface Variant {
  id: number;
  label: string;
  price: string;
  is_default: boolean;
}

interface Modifier {
  id: number;
  name: string;
  price_adjustment: string;
}

interface MenuItemFull {
  id: number;
  name: string;
  description: string;
  is_active: boolean;
  sort_order: number;
  variants: Variant[];
  modifiers: Modifier[];
}

interface Category {
  id: number;
  name: string;
  sort_order: number;
  is_active: boolean;
  items: MenuItemFull[];
}

interface FullMenu {
  restaurant_name: string;
  categories: Category[];
}

export default function MenuManagementPage() {
  const params = useParams<{ slug: string }>();
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();
  const [menu, setMenu] = useState<FullMenu | null>(null);
  const [loading, setLoading] = useState(true);
  const [newCategoryName, setNewCategoryName] = useState("");
  const [showAddItem, setShowAddItem] = useState<number | null>(null);
  const [newItem, setNewItem] = useState({
    name: "",
    description: "",
    variantLabel: "Regular",
    variantPrice: "",
  });

  useEffect(() => {
    if (!isAuthenticated) {
      router.push("/admin/login");
      return;
    }
    loadMenu();
  }, [isAuthenticated, router]);

  const loadMenu = async () => {
    try {
      const data = await apiFetch<FullMenu>(
        `/api/restaurants/${params.slug}/menu/`
      );
      setMenu(data);
    } catch {
      // Handle error
    } finally {
      setLoading(false);
    }
  };

  const handleAddCategory = async (e: React.FormEvent) => {
    e.preventDefault();
    await apiFetch(`/api/restaurants/${params.slug}/categories/`, {
      method: "POST",
      body: JSON.stringify({
        name: newCategoryName,
        sort_order: (menu?.categories.length || 0) + 1,
      }),
    });
    setNewCategoryName("");
    loadMenu();
  };

  const handleAddItem = async (categoryId: number) => {
    await apiFetch(`/api/restaurants/${params.slug}/items/`, {
      method: "POST",
      body: JSON.stringify({
        category_id: categoryId,
        name: newItem.name,
        description: newItem.description,
        sort_order: 0,
        variants: [
          {
            label: newItem.variantLabel,
            price: newItem.variantPrice,
            is_default: true,
          },
        ],
        modifiers: [],
      }),
    });
    setShowAddItem(null);
    setNewItem({ name: "", description: "", variantLabel: "Regular", variantPrice: "" });
    loadMenu();
  };

  const handleDeactivateItem = async (itemId: number) => {
    await apiFetch(`/api/restaurants/${params.slug}/items/${itemId}/`, {
      method: "DELETE",
    });
    loadMenu();
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
        <div className="flex items-center justify-between mb-6">
          <div>
            <Link
              href="/admin"
              className="text-sm text-muted-foreground hover:underline"
            >
              Back to dashboard
            </Link>
            <h1 className="text-2xl font-bold">
              {menu?.restaurant_name} - Menu
            </h1>
          </div>
        </div>

        {/* Add Category */}
        <Card className="p-4 mb-6">
          <form onSubmit={handleAddCategory} className="flex gap-2">
            <Input
              value={newCategoryName}
              onChange={(e) => setNewCategoryName(e.target.value)}
              placeholder="New category name (e.g. Appetizers)"
              required
            />
            <Button type="submit">Add Category</Button>
          </form>
        </Card>

        {/* Categories and Items */}
        {menu?.categories.map((cat) => (
          <div key={cat.id} className="mb-8">
            <h2 className="text-xl font-semibold mb-3">{cat.name}</h2>

            <div className="space-y-2 mb-4">
              {cat.items.map((item) => (
                <Card
                  key={item.id}
                  className={`p-4 ${!item.is_active ? "opacity-50" : ""}`}
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{item.name}</span>
                        {!item.is_active && (
                          <Badge variant="secondary">Inactive</Badge>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {item.description}
                      </p>
                      <div className="text-sm mt-1">
                        {item.variants.map((v) => (
                          <span key={v.id} className="mr-3">
                            {v.label}: ${v.price}
                            {v.is_default && " (default)"}
                          </span>
                        ))}
                      </div>
                      {item.modifiers.length > 0 && (
                        <div className="text-sm text-muted-foreground mt-1">
                          Modifiers:{" "}
                          {item.modifiers
                            .map(
                              (m) =>
                                `${m.name} (+$${m.price_adjustment})`
                            )
                            .join(", ")}
                        </div>
                      )}
                    </div>
                    {item.is_active && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDeactivateItem(item.id)}
                      >
                        Remove
                      </Button>
                    )}
                  </div>
                </Card>
              ))}
            </div>

            {/* Add Item Form */}
            {showAddItem === cat.id ? (
              <Card className="p-4">
                <div className="space-y-3">
                  <div>
                    <Label>Item Name</Label>
                    <Input
                      value={newItem.name}
                      onChange={(e) =>
                        setNewItem({ ...newItem, name: e.target.value })
                      }
                      placeholder="e.g. Margherita Pizza"
                    />
                  </div>
                  <div>
                    <Label>Description</Label>
                    <Input
                      value={newItem.description}
                      onChange={(e) =>
                        setNewItem({ ...newItem, description: e.target.value })
                      }
                      placeholder="Classic pizza with tomato and mozzarella"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label>Size/Variant Label</Label>
                      <Input
                        value={newItem.variantLabel}
                        onChange={(e) =>
                          setNewItem({
                            ...newItem,
                            variantLabel: e.target.value,
                          })
                        }
                        placeholder="Regular"
                      />
                    </div>
                    <div>
                      <Label>Price</Label>
                      <Input
                        type="number"
                        step="0.01"
                        value={newItem.variantPrice}
                        onChange={(e) =>
                          setNewItem({
                            ...newItem,
                            variantPrice: e.target.value,
                          })
                        }
                        placeholder="12.99"
                      />
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button onClick={() => handleAddItem(cat.id)}>
                      Save Item
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => setShowAddItem(null)}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              </Card>
            ) : (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowAddItem(cat.id)}
              >
                + Add Item to {cat.name}
              </Button>
            )}

            <Separator className="mt-6" />
          </div>
        ))}
      </div>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/
git commit -m "feat: add admin menu management page with category and item CRUD"
```

---

## Task 7: Settings Page with QR Code Generator

**Files:**
- Create: `frontend/src/app/admin/[slug]/settings/page.tsx`

**Step 1: Create settings page**

Create `frontend/src/app/admin/[slug]/settings/page.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { QRCodeSVG } from "qrcode.react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function SettingsPage() {
  const params = useParams<{ slug: string }>();
  const [tableIds, setTableIds] = useState("");
  const [generatedTables, setGeneratedTables] = useState<string[]>([]);

  const baseUrl = typeof window !== "undefined" ? window.location.origin : "";

  const handleGenerate = () => {
    const ids = tableIds
      .split(",")
      .map((id) => id.trim())
      .filter(Boolean);
    setGeneratedTables(ids);
  };

  const getOrderUrl = (tableId?: string) => {
    if (tableId) {
      return `${baseUrl}/order/${params.slug}/${tableId}`;
    }
    return `${baseUrl}/order/${params.slug}`;
  };

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-4xl mx-auto">
        <Link
          href="/admin"
          className="text-sm text-muted-foreground hover:underline"
        >
          Back to dashboard
        </Link>
        <h1 className="text-2xl font-bold mb-6">Settings & QR Codes</h1>

        {/* Counter QR (no table) */}
        <Card className="p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">
            Counter / Pickup QR Code
          </h2>
          <p className="text-sm text-muted-foreground mb-4">
            For counter service without table numbers.
          </p>
          <div className="flex items-center gap-6">
            <QRCodeSVG value={getOrderUrl()} size={150} />
            <div>
              <p className="text-sm font-mono break-all">{getOrderUrl()}</p>
            </div>
          </div>
        </Card>

        {/* Table QR Generator */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold mb-4">Table QR Codes</h2>
          <div className="flex gap-2 mb-4">
            <div className="flex-1">
              <Label>Table IDs (comma-separated)</Label>
              <Input
                value={tableIds}
                onChange={(e) => setTableIds(e.target.value)}
                placeholder="1, 2, 3, 4, 5"
              />
            </div>
            <Button className="mt-6" onClick={handleGenerate}>
              Generate
            </Button>
          </div>

          {generatedTables.length > 0 && (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-6 mt-6">
              {generatedTables.map((tableId) => (
                <div
                  key={tableId}
                  className="flex flex-col items-center p-4 border rounded-lg"
                >
                  <QRCodeSVG value={getOrderUrl(tableId)} size={120} />
                  <p className="font-semibold mt-2">Table {tableId}</p>
                  <p className="text-xs text-muted-foreground break-all text-center">
                    {getOrderUrl(tableId)}
                  </p>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/
git commit -m "feat: add settings page with QR code generator for tables"
```

---

## Task 8: Order History Page (Admin)

**Files:**
- Create: `frontend/src/app/admin/[slug]/orders/page.tsx`

**Step 1: Create orders page**

Create `frontend/src/app/admin/[slug]/orders/page.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useAuthStore } from "@/stores/auth-store";
import { apiFetch } from "@/lib/api";
import type { OrderResponse } from "@/types";

const statusVariant: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  pending: "outline",
  confirmed: "destructive",
  preparing: "secondary",
  ready: "default",
  completed: "outline",
};

export default function OrderHistoryPage() {
  const params = useParams<{ slug: string }>();
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();
  const [orders, setOrders] = useState<OrderResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isAuthenticated) {
      router.push("/admin/login");
      return;
    }
    // Note: This would need a backend endpoint for listing restaurant orders.
    // For MVP, this is a placeholder that can be wired up after adding the endpoint.
    setLoading(false);
  }, [isAuthenticated, router]);

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
        <Link
          href="/admin"
          className="text-sm text-muted-foreground hover:underline"
        >
          Back to dashboard
        </Link>
        <h1 className="text-2xl font-bold mb-6">Order History</h1>

        <div className="space-y-3">
          {orders.map((order) => (
            <Card key={order.id} className="p-4">
              <div className="flex justify-between items-start">
                <div>
                  <span className="font-mono text-sm">
                    #{order.id.slice(0, 8)}
                  </span>
                  {order.table_identifier && (
                    <span className="text-sm text-muted-foreground ml-2">
                      Table {order.table_identifier}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={statusVariant[order.status] || "outline"}>
                    {order.status}
                  </Badge>
                  <span className="font-semibold">${order.total_price}</span>
                </div>
              </div>
              <ul className="text-sm mt-2 text-muted-foreground">
                {order.items.map((item) => (
                  <li key={item.id}>
                    {item.quantity}x {item.name} ({item.variant_label})
                  </li>
                ))}
              </ul>
            </Card>
          ))}
          {orders.length === 0 && (
            <p className="text-center text-muted-foreground py-12">
              No orders yet. Orders will appear here once customers start
              ordering.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
```

**Step 2: Verify full frontend build**

```bash
cd frontend
npm run build
```

Expected: Build succeeds.

**Step 3: Commit**

```bash
git add frontend/src/
git commit -m "feat: add admin order history page (placeholder)"
```
