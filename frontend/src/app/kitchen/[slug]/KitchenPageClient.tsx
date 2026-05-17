"use client";

import "./print.css";
import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useKitchenStore } from "@/stores/kitchen-store";
import { useWebSocket } from "@/hooks/use-websocket";
import { useWsToken } from "@/hooks/use-ws-token";
import { useAuthStore } from "@/stores/auth-store";
import { useMyRestaurants } from "@/hooks/use-my-restaurants";
import { useAdvanceOrder } from "@/hooks/use-advance-order";
import { useRestaurantOrders } from "@/hooks/use-restaurant-orders";
import { OrderColumn } from "./components/OrderColumn";
import { PauseOrdersButton } from "./components/PauseOrdersButton";
import { ChefHat } from "lucide-react";
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

  const { data: wsToken } = useWsToken(authorized);

  const { isConnected } = useWebSocket({
    url: `${WS_URL}/ws/kitchen/${slug}/?token=${wsToken ?? ""}`,
    onMessage: handleMessage,
    enabled: authorized && !!wsToken,
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

  const restaurantName = restaurants?.find((r) => r.slug === slug)?.name ?? slug;

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="bg-card/50 border-b border-border px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ChefHat className="w-5 h-5 text-primary" />
          <span className="font-semibold text-foreground">{restaurantName}</span>
        </div>
        <div className="flex items-center gap-3">
          <PauseOrdersButton slug={slug} />
          <div className="flex items-center gap-2">
            <div
              className={`w-2 h-2 rounded-full ${
                isConnected
                  ? "bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.4)]"
                  : "bg-destructive"
              }`}
            />
            <span className="text-xs text-muted-foreground">
              {isConnected ? "Live" : "Disconnected"}
            </span>
          </div>
        </div>
      </div>

      {/* Kanban board */}
      <div className="grid grid-cols-3 gap-3 p-4">
        <OrderColumn
          title="New"
          orders={confirmed}
          onAdvance={handleAdvance}
          columnType="new"
        />
        <OrderColumn
          title="Preparing"
          orders={preparing}
          onAdvance={handleAdvance}
          columnType="preparing"
        />
        <OrderColumn
          title="Ready"
          orders={ready}
          onAdvance={handleAdvance}
          columnType="ready"
        />
      </div>
    </div>
  );
}
