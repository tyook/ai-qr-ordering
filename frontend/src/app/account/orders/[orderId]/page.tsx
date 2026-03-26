"use client";

import { useRouter, useParams } from "next/navigation";
import { ArrowLeft, CreditCard } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { useRequireAuth } from "@/hooks/use-auth";
import { useOrderDetail } from "@/hooks/use-orders";

const statusConfig: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  pending_payment: { label: "Pending Payment", variant: "destructive" },
  pending: { label: "Pending", variant: "secondary" },
  confirmed: { label: "Confirmed", variant: "default" },
  preparing: { label: "Preparing", variant: "default" },
  ready: { label: "Ready", variant: "default" },
  completed: { label: "Completed", variant: "outline" },
};

const paymentStatusConfig: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  pending: { label: "Pending", variant: "secondary" },
  paid: { label: "Paid", variant: "default" },
  failed: { label: "Failed", variant: "destructive" },
  refunded: { label: "Refunded", variant: "outline" },
};

export default function OrderDetailPage() {
  const router = useRouter();
  const params = useParams();
  const orderId = params.orderId as string;
  const isAuthenticated = useRequireAuth();
  const { data: order, isLoading, error } = useOrderDetail(orderId);

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

  if (error || !order) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-8 text-center">
        <p className="text-destructive">Failed to load order.</p>
        <p className="text-sm text-muted-foreground mt-2">
          {error instanceof Error ? error.message : "Order not found"}
        </p>
        <Button variant="outline" className="mt-4" onClick={() => router.push("/account/orders")}>
          Back to Orders
        </Button>
      </div>
    );
  }

  const orderStatus = statusConfig[order.status] || { label: order.status, variant: "secondary" as const };
  const paymentStatus = paymentStatusConfig[order.payment_status] || { label: order.payment_status, variant: "secondary" as const };

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <Button variant="ghost" size="icon" onClick={() => router.push("/account/orders")}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold">Order Details</h1>
          <p className="text-sm text-muted-foreground">
            #{order.id.slice(0, 8)}
          </p>
        </div>
        <Badge variant={orderStatus.variant}>{orderStatus.label}</Badge>
      </div>

      {/* Restaurant & Date */}
      <Card className="p-4 mb-4">
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
        {order.table_identifier && (
          <p className="text-sm text-muted-foreground mt-1">
            Table: {order.table_identifier}
          </p>
        )}
      </Card>

      {/* Menu Items */}
      <Card className="p-4 mb-4">
        <h2 className="font-semibold text-lg mb-3">Items</h2>
        <div className="space-y-3">
          {order.items.map((item, index) => (
            <div key={item.id}>
              {index > 0 && <Separator className="mb-3" />}
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <p className="font-medium">
                    {item.quantity}x {item.name}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {item.variant_label}
                  </p>
                  {item.special_requests && (
                    <p className="text-sm text-muted-foreground italic mt-1">
                      Note: {item.special_requests}
                    </p>
                  )}
                </div>
                <p className="font-medium text-sm">
                  ${(Number(item.variant_price) * item.quantity).toFixed(2)}
                </p>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Invoice Breakdown */}
      <Card className="p-4 mb-4">
        <h2 className="font-semibold text-lg mb-3">Invoice</h2>
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Subtotal</span>
            <span>${Number(order.subtotal).toFixed(2)}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">
              Tax ({(Number(order.tax_rate) * 100).toFixed(1)}%)
            </span>
            <span>${Number(order.tax_amount).toFixed(2)}</span>
          </div>
          <Separator />
          <div className="flex justify-between font-bold">
            <span>Total</span>
            <span>${Number(order.total_price).toFixed(2)}</span>
          </div>
        </div>
      </Card>

      {/* Payment Info */}
      <Card className="p-4">
        <h2 className="font-semibold text-lg mb-3">Payment</h2>
        <div className="space-y-2">
          <div className="flex justify-between items-center">
            <span className="text-sm text-muted-foreground">Status</span>
            <Badge variant={paymentStatus.variant}>{paymentStatus.label}</Badge>
          </div>
          {order.payment_method && (
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Method</span>
              <div className="flex items-center gap-2">
                <CreditCard className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm capitalize">
                  {order.payment_method.brand} ending in {order.payment_method.last4}
                </span>
              </div>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
