"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useKitchenStore } from "@/stores/kitchen-store";
import { useWebSocket } from "@/hooks/use-websocket";
import { useAuthStore } from "@/stores/auth-store";
import { useMyRestaurants } from "@/hooks/use-my-restaurants";
import { useAdvanceOrder } from "@/hooks/use-advance-order";
import { useRestaurantOrders } from "@/hooks/use-restaurant-orders";
import { OrderColumn } from "./components/OrderColumn";
import { Badge } from "@/components/ui/badge";
import type { OrderResponse } from "@/types";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:5005";

const NEXT_STATUS: Record<string, string> = {
  confirmed: "preparing",
  preparing: "ready",
  ready: "completed",
};

export default function KitchenPage() {
  const params = useParams<{ slug: string }>();
  const slug = params.slug;
  const router = useRouter();
  const { isAuthenticated, checkAuth } = useAuthStore();

  useEffect(() => {
    if (isAuthenticated === null) checkAuth();
  }, [isAuthenticated, checkAuth]);
  const { orders, addOrUpdateOrder, setOrders } = useKitchenStore();
  const [authorized, setAuthorized] = useState(false);

  const { data: restaurants, isLoading: checking } = useMyRestaurants(isAuthenticated ?? false);
  const advanceOrder = useAdvanceOrder();

  // Auth guard: verify user is owner/staff of this restaurant
  useEffect(() => {
    if (isAuthenticated === null) return; // still checking
    if (isAuthenticated === false) {
      router.replace("/");
      return;
    }

    if (!checking && restaurants) {
      const hasAccess = restaurants.some((r) => r.slug === slug);
      if (!hasAccess) {
        router.replace("/");
      } else {
        setAuthorized(true);
      }
    }
  }, [isAuthenticated, checking, restaurants, slug, router]);

  // Seed store with existing active orders on mount
  const { data: existingOrders } = useRestaurantOrders(authorized ? slug : "");

  useEffect(() => {
    if (existingOrders) {
      const active = existingOrders.filter(
        (o) => o.status === "confirmed" || o.status === "preparing" || o.status === "ready"
      );
      setOrders(active);
    }
  }, [existingOrders, setOrders]);

  const handleMessage = useCallback(
    (data: unknown) => {
      addOrUpdateOrder(data as OrderResponse);
    },
    [addOrUpdateOrder]
  );

  const token =
    typeof window !== "undefined" ? localStorage.getItem("access_token") : null;

  const { isConnected } = useWebSocket({
    url: `${WS_URL}/ws/kitchen/${slug}/?token=${token ?? ""}`,
    onMessage: handleMessage,
    enabled: authorized,
  });

  const handleAdvance = (orderId: string) => {
    const order = orders.find((o) => o.id === orderId);
    if (!order) return;

    const nextStatus = NEXT_STATUS[order.status];
    if (!nextStatus) return;

    advanceOrder.mutate(
      { orderId, nextStatus },
      {
        onSuccess: (updated) => {
          addOrUpdateOrder(updated);
        },
      }
    );
  };

  if (checking || !authorized) {
    return null;
  }

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
