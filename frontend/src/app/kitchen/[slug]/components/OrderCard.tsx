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
