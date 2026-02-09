"use client";

import { useOrderStore } from "@/stores/order-store";

export function SubmittedStep() {
  const { orderId, tableIdentifier } = useOrderStore();

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
      <div className="text-4xl mb-4">&#10003;</div>
      <h2 className="text-2xl font-bold mb-2">Order Placed!</h2>
      {orderId && (
        <p className="text-muted-foreground mb-1">
          Order #{orderId.slice(0, 8)}
        </p>
      )}
      {tableIdentifier && (
        <p className="text-muted-foreground">Table {tableIdentifier}</p>
      )}
      <p className="text-sm text-muted-foreground mt-4">
        Your order has been sent to the kitchen.
      </p>
    </div>
  );
}
