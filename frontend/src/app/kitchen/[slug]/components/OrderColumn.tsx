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
