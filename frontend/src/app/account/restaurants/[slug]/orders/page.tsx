"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useRequireRestaurantAccess } from "@/hooks/use-auth";
import { useRestaurantOrders } from "@/hooks/use-restaurant-orders";

const statusVariant: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  pending_payment: "destructive",
  pending: "outline",
  confirmed: "destructive",
  preparing: "secondary",
  ready: "default",
  completed: "outline",
};

export default function OrderHistoryPage() {
  const params = useParams();
  const slug = params.slug as string;
  const isAuthenticated = useRequireRestaurantAccess();
  const { data: orders, isLoading, error } = useRestaurantOrders(slug);

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

  if (error) {
    return (
      <div className="min-h-screen bg-background p-6">
        <div className="max-w-4xl mx-auto text-center py-12">
          <p className="text-destructive">Failed to load orders.</p>
          <p className="text-sm text-muted-foreground mt-2">
            {error instanceof Error ? error.message : "Unknown error"}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-4xl mx-auto">
        <Link
          href="/account/restaurants"
          className="text-sm text-muted-foreground hover:underline"
        >
          Back to dashboard
        </Link>
        <h1 className="text-2xl font-bold mb-6">Order History</h1>

        <div className="space-y-3">
          {orders && orders.length > 0 ? (
            orders.map((order) => (
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
                    <p className="text-xs text-muted-foreground mt-1">
                      {new Date(order.created_at).toLocaleDateString("en-US", {
                        year: "numeric",
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </p>
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
            ))
          ) : (
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
