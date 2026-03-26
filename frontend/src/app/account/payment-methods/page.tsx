"use client";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useRequireAuth } from "@/hooks/use-auth";
import {
  usePaymentMethods,
  useDeletePaymentMethod,
} from "@/hooks/use-payment-methods";

export default function PaymentMethodsPage() {
  const isAuthenticated = useRequireAuth();
  const { data: methods, isLoading, error } = usePaymentMethods();
  const deleteMutation = useDeletePaymentMethod();

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
        <p className="text-destructive">Failed to load payment methods.</p>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">Payment Methods</h1>
      {!methods || methods.length === 0 ? (
        <Card className="p-8 text-center">
          <p className="text-muted-foreground">No saved payment methods.</p>
          <p className="text-sm text-muted-foreground mt-2">
            You can save a card during checkout for faster future payments.
          </p>
        </Card>
      ) : (
        <div className="space-y-3">
          {methods.map((method) => (
            <Card
              key={method.id}
              className="p-4 flex items-center justify-between"
            >
              <div>
                <span className="font-medium capitalize">{method.brand}</span>
                <span className="text-muted-foreground">
                  {" "}
                  ending in {method.last4}
                </span>
                <p className="text-sm text-muted-foreground mt-1">
                  Expires {String(method.exp_month).padStart(2, "0")}/
                  {method.exp_year}
                </p>
              </div>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => deleteMutation.mutate(method.id)}
                disabled={deleteMutation.isPending}
              >
                {deleteMutation.isPending ? "Removing..." : "Remove"}
              </Button>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
