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
