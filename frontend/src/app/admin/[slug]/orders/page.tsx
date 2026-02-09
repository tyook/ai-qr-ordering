"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useAuthStore } from "@/stores/auth-store";
import type { OrderResponse } from "@/types";

const statusVariant: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  pending: "outline",
  confirmed: "destructive",
  preparing: "secondary",
  ready: "default",
  completed: "outline",
};

export default function OrderHistoryPage() {
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();
  const [orders] = useState<OrderResponse[]>([]);
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
