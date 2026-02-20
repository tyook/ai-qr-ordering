"use client";

import { useState } from "react";
import {
  Elements,
  PaymentElement,
  useStripe,
  useElements,
} from "@stripe/react-stripe-js";
import { loadStripe } from "@stripe/stripe-js";
import { Button } from "@/components/ui/button";
import { useOrderStore } from "@/stores/order-store";
import { useCustomerAuthStore } from "@/stores/customer-auth-store";
import { usePaymentMethods } from "@/hooks/use-payment-methods";
import { createPayment } from "@/lib/api";
import type { SavedPaymentMethod, ConfirmOrderItem } from "@/types";

const stripePromise = loadStripe(
  process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY || ""
);

function SavedCardOption({
  method,
  selected,
  onSelect,
}: {
  method: SavedPaymentMethod;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <label
      className={`flex items-center gap-3 p-3 border rounded-lg cursor-pointer transition-colors ${
        selected ? "border-primary bg-primary/5" : "border-border hover:border-primary/50"
      }`}
    >
      <input
        type="radio"
        name="payment-method"
        checked={selected}
        onChange={onSelect}
        className="accent-primary"
      />
      <div className="flex-1">
        <span className="font-medium capitalize">{method.brand}</span>
        <span className="text-muted-foreground"> ending in {method.last4}</span>
      </div>
      <span className="text-sm text-muted-foreground">
        {String(method.exp_month).padStart(2, "0")}/{method.exp_year}
      </span>
    </label>
  );
}

function PaymentForm() {
  const stripe = useStripe();
  const elements = useElements();
  const { setStep } = useOrderStore();
  const [isProcessing, setIsProcessing] = useState(false);
  const [paymentError, setPaymentError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!stripe || !elements) return;

    setIsProcessing(true);
    setPaymentError(null);

    const { error } = await stripe.confirmPayment({
      elements,
      confirmParams: {
        return_url: window.location.href,
      },
      redirect: "if_required",
    });

    if (error) {
      setPaymentError(error.message || "Payment failed. Please try again.");
      setIsProcessing(false);
    } else {
      setStep("submitted");
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <PaymentElement />
      {paymentError && (
        <p className="text-destructive text-sm mt-4">{paymentError}</p>
      )}
      <Button
        type="submit"
        className="w-full mt-6"
        disabled={!stripe || isProcessing}
      >
        {isProcessing ? "Processing payment..." : "Pay Now"}
      </Button>
    </form>
  );
}

interface PaymentStepProps {
  taxRate: string;
}

export function PaymentStep({ taxRate }: PaymentStepProps) {
  const {
    clientSecret,
    totalPrice,
    setStep,
    setClientSecret,
    parsedItems,
    rawInput,
    tableIdentifier,
    language,
    customerName,
    customerPhone,
    setOrderId,
  } = useOrderStore();
  const { isAuthenticated } = useCustomerAuthStore();
  const { data: savedMethods } = usePaymentMethods();
  const [selectedMethodId, setSelectedMethodId] = useState<string | null>(null);
  const [useNewCard, setUseNewCard] = useState(false);
  const [saveCard, setSaveCard] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [paymentError, setPaymentError] = useState<string | null>(null);

  const hasSavedCards = isAuthenticated && savedMethods && savedMethods.length > 0;

  // Auto-select first saved card if available and nothing selected yet
  const effectiveSelectedId =
    selectedMethodId ?? (hasSavedCards && !useNewCard ? savedMethods[0].id : null);

  const subtotal = parseFloat(totalPrice);
  const tax = (subtotal * parseFloat(taxRate)) / 100;
  const total = subtotal + tax;

  const slug = typeof window !== "undefined"
    ? window.location.pathname.split("/")[2]
    : "";

  const handleSavedCardPayment = async () => {
    if (!effectiveSelectedId) return;

    setIsProcessing(true);
    setPaymentError(null);

    try {
      const items: ConfirmOrderItem[] = parsedItems.map((item) => ({
        menu_item_id: item.menu_item_id,
        variant_id: item.variant.id,
        quantity: item.quantity,
        modifier_ids: item.modifiers.map((m) => m.id),
        special_requests: item.special_requests,
      }));

      const response = await createPayment(
        slug,
        items,
        rawInput,
        tableIdentifier,
        language,
        customerName,
        customerPhone,
        effectiveSelectedId,
        false,
      );

      setOrderId(response.id);

      if (response.status === "confirmed") {
        setStep("submitted");
      } else {
        // Payment requires further action — fall back to Payment Element
        setClientSecret(response.client_secret);
        setUseNewCard(true);
      }
    } catch (err) {
      setPaymentError(
        err instanceof Error ? err.message : "Payment failed. Please try again."
      );
    } finally {
      setIsProcessing(false);
    }
  };

  if (!clientSecret && !hasSavedCards) {
    return (
      <div className="max-w-lg mx-auto px-4 py-8 text-center">
        <p className="text-muted-foreground mb-4">
          Payment session expired. Please try again.
        </p>
        <Button onClick={() => setStep("confirmation")}>Go Back</Button>
      </div>
    );
  }

  return (
    <div className="max-w-lg mx-auto px-4 py-8">
      <h2 className="text-xl font-semibold mb-2">Payment</h2>
      <p className="text-muted-foreground mb-6">Total: ${total.toFixed(2)}</p>

      {hasSavedCards && !useNewCard ? (
        <div className="space-y-4">
          <div className="space-y-2">
            {savedMethods.map((method) => (
              <SavedCardOption
                key={method.id}
                method={method}
                selected={effectiveSelectedId === method.id}
                onSelect={() => {
                  setSelectedMethodId(method.id);
                  setUseNewCard(false);
                }}
              />
            ))}
            <label
              className={`flex items-center gap-3 p-3 border rounded-lg cursor-pointer transition-colors ${
                useNewCard
                  ? "border-primary bg-primary/5"
                  : "border-border hover:border-primary/50"
              }`}
            >
              <input
                type="radio"
                name="payment-method"
                checked={useNewCard}
                onChange={() => setUseNewCard(true)}
                className="accent-primary"
              />
              <span className="font-medium">Add new card</span>
            </label>
          </div>

          {paymentError && (
            <p className="text-destructive text-sm">{paymentError}</p>
          )}

          <Button
            className="w-full"
            onClick={handleSavedCardPayment}
            disabled={isProcessing}
          >
            {isProcessing ? "Processing payment..." : "Pay Now"}
          </Button>
        </div>
      ) : clientSecret ? (
        <div>
          {isAuthenticated && (
            <label className="flex items-center gap-2 mb-4">
              <input
                type="checkbox"
                checked={saveCard}
                onChange={(e) => setSaveCard(e.target.checked)}
                className="accent-primary"
              />
              <span className="text-sm">Save this card for future orders</span>
            </label>
          )}
          <Elements
            stripe={stripePromise}
            options={{
              clientSecret,
              appearance: { theme: "stripe" },
            }}
          >
            <PaymentForm />
          </Elements>
          {hasSavedCards && (
            <Button
              variant="ghost"
              className="w-full mt-2"
              onClick={() => setUseNewCard(false)}
            >
              Use a saved card
            </Button>
          )}
        </div>
      ) : null}

      <Button
        variant="ghost"
        className="w-full mt-4"
        onClick={() => setStep("confirmation")}
      >
        Back to order
      </Button>
    </div>
  );
}
