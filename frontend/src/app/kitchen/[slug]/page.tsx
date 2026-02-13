"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useKitchenStore } from "@/stores/kitchen-store";
import { useWebSocket } from "@/hooks/use-websocket";
import { useAuthStore } from "@/stores/auth-store";
import { apiFetch } from "@/lib/api";
import { OrderColumn } from "./components/OrderColumn";
import { Badge } from "@/components/ui/badge";
import type { OrderResponse } from "@/types";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:5005";

const NEXT_STATUS: Record<string, string> = {
  confirmed: "preparing",
  preparing: "ready",
  ready: "completed",
};

interface Restaurant {
  slug: string;
  [key: string]: unknown;
}

export default function KitchenPage() {
  const params = useParams<{ slug: string }>();
  const slug = params.slug;
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();
  const { orders, addOrUpdateOrder } = useKitchenStore();
  const [authorized, setAuthorized] = useState(false);
  const [checking, setChecking] = useState(true);

  // Auth guard: verify user is owner/staff of this restaurant
  useEffect(() => {
    if (!isAuthenticated) {
      router.replace("/");
      return;
    }

    apiFetch<{ results: Restaurant[] }>("/api/restaurants/me/")
      .then((data) => {
        const hasAccess = data.results.some((r) => r.slug === slug);
        if (!hasAccess) {
          router.replace("/");
        } else {
          setAuthorized(true);
        }
      })
      .catch(() => {
        router.replace("/");
      })
      .finally(() => {
        setChecking(false);
      });
  }, [isAuthenticated, slug, router]);

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

  const handleAdvance = async (orderId: string) => {
    const order = orders.find((o) => o.id === orderId);
    if (!order) return;

    const nextStatus = NEXT_STATUS[order.status];
    if (!nextStatus) return;

    try {
      const updated = await apiFetch<OrderResponse>(
        `/api/kitchen/orders/${orderId}/`,
        {
          method: "PATCH",
          body: JSON.stringify({ status: nextStatus }),
        }
      );
      addOrUpdateOrder(updated);
    } catch {
      // Handle error silently for now
    }
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
