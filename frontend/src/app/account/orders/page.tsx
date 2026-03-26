"use client";

import { useRouter } from "next/navigation";
import { Card } from "@/components/ui/card";
import { useRequireAuth } from "@/hooks/use-auth";
import { useOrderHistory } from "@/hooks/use-orders";

export default function CustomerOrdersPage() {
  const router = useRouter();
  const isAuthenticated = useRequireAuth();
  const { data: orders, isLoading, error } = useOrderHistory();

  if (isAuthenticated === null || isLoading) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto" />
      </div>
    );
  }

  if (isAuthenticated === false) {
    return null;
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-8 text-center">
        <p className="text-destructive">Failed to load orders.</p>
        <p className="text-sm text-muted-foreground mt-2">
          {error instanceof Error ? error.message : "Unknown error"}
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">Your Orders</h1>
      {!orders || orders.length === 0 ? (
        <Card className="p-8 text-center">
          <p className="text-muted-foreground">No orders yet.</p>
          <p className="text-sm text-muted-foreground mt-2">
            Your order history will appear here after you place an order.
          </p>
        </Card>
      ) : (
        <div className="space-y-4">
          {orders.map((order) => (
            <Card
              key={order.id}
              className="p-4 cursor-pointer hover:shadow-md transition-shadow"
              onClick={() => router.push(`/account/orders/${order.id}`)}
            >
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <p className="font-medium text-lg">{order.restaurant_name}</p>
                  <p className="text-sm text-muted-foreground mt-1">
                    {new Date(order.created_at).toLocaleDateString("en-US", {
                      year: "numeric",
                      month: "long",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </p>
                  <p className="text-sm text-muted-foreground mt-1">
                    {order.items.length} item{order.items.length !== 1 ? "s" : ""}
                  </p>
                  {order.table_identifier && (
                    <p className="text-sm text-muted-foreground">
                      Table: {order.table_identifier}
                    </p>
                  )}
                </div>
                <div className="text-right">
                  <p className="font-bold text-lg">${order.total_price}</p>
                  <p className="text-xs text-muted-foreground capitalize mt-1 px-2 py-1 bg-secondary rounded">
                    {order.status}
                  </p>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
