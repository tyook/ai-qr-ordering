"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Elements,
  PaymentElement,
  useStripe,
  useElements,
} from "@stripe/react-stripe-js";
import type { Appearance } from "@stripe/stripe-js";
import { loadStripe } from "@stripe/stripe-js";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useOrderStore } from "@/stores/order-store";
import { useAuthStore } from "@/stores/auth-store";
import { usePaymentMethods } from "@/hooks/use-payment-methods";
import { confirmPayment, confirmTabPayment, createPayment, saveCardConsent } from "@/lib/api";
import type { SavedPaymentMethod, ConfirmOrderItem } from "@/types";

function PaymentOverlay({ visible }: { visible: boolean }) {
  if (!visible) return null;

  return (
    <div className="fixed inset-0 z-[9999] flex flex-col items-center justify-center bg-background/80 backdrop-blur-sm">
      <Loader2 className="h-12 w-12 animate-spin text-primary mb-4" />
      <p className="text-lg font-semibold text-foreground">Processing payment...</p>
      <p className="text-sm text-muted-foreground mt-1">Please don&apos;t close this page</p>
    </div>
  );
}

const stripePromise = loadStripe(
  process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY || ""
);

const stripeAppearance: Appearance = {
  theme: "night",
  variables: {
    colorPrimary: "#d97706",
    colorBackground: "#1e293b",
    colorText: "#f1f5f9",
    colorTextSecondary: "#94a3b8",
    colorDanger: "#ef4444",
    fontFamily: "var(--font-geist-sans)",
    borderRadius: "12px",
    spacingUnit: "4px",
  },
  rules: {
    ".Input": {
      backgroundColor: "#334155",
      border: "1px solid rgba(255,255,255,0.06)",
    },
  },
};

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

function PaymentForm({
  saveCard,
  slug,
  orderId,
}: {
  saveCard: boolean;
  slug: string;
  orderId: string | null;
}) {
  const stripe = useStripe();
  const elements = useElements();
  const router = useRouter();
  const { setStep, paymentModel, tabPaymentId } = useOrderStore();
  const [isProcessing, setIsProcessing] = useState(false);
  const [paymentError, setPaymentError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!stripe || !elements) return;

    setIsProcessing(true);
    setPaymentError(null);

    // If user consented to save card, update the PaymentIntent before confirming
    if (saveCard && slug && orderId) {
      try {
        await saveCardConsent(slug, orderId);
      } catch {
        // Non-fatal — proceed with payment even if save-card update fails
      }
    }

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
      if (paymentModel === "tab") {
        if (slug && tabPaymentId) {
          try {
            const updatedTab = await confirmTabPayment(slug, tabPaymentId);
            useOrderStore.getState().setTabData(updatedTab);
            if (parseFloat(updatedTab.amount_remaining) <= 0) {
              setStep("tab_closed");
              return;
            }
          } catch {
            // Non-fatal: webhook will eventually confirm
          }
        }
        setStep("submitted");
      } else {
        if (slug && orderId) {
          try {
            await confirmPayment(slug, orderId);
          } catch {
            // Non-fatal: webhook will eventually confirm the order
          }
        }
        if (slug && orderId) {
          router.push(`/order/${slug}/status/${orderId}`);
        } else {
          setStep("submitted");
        }
      }
    }
  };

  return (
    <>
      <PaymentOverlay visible={isProcessing} />
      <form onSubmit={handleSubmit}>
        <PaymentElement />
        {paymentError && (
          <p className="text-destructive text-sm mt-4">{paymentError}</p>
        )}
        <Button
          type="submit"
          variant="gradient"
          size="lg"
          className="w-full glow-primary mt-4"
          disabled={!stripe || isProcessing}
        >
          {isProcessing ? "Processing payment..." : "Pay Now"}
        </Button>
      </form>
    </>
  );
}

interface PaymentStepProps {
  taxRate: string;
}

export function PaymentStep({ taxRate }: PaymentStepProps) {
  const router = useRouter();
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
    orderId,
    setOrderId,
    paymentModel,
  } = useOrderStore();
  const { isAuthenticated } = useAuthStore();
  const { data: savedMethods } = usePaymentMethods();
  const [selectedMethodId, setSelectedMethodId] = useState<string | null>(null);
  const [useNewCard, setUseNewCard] = useState(false);
  const [saveCard, setSaveCard] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [paymentError, setPaymentError] = useState<string | null>(null);

  const isTabPayment = paymentModel === "tab";
  const hasSavedCards = !isTabPayment && isAuthenticated && savedMethods && savedMethods.length > 0;

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
        router.push(`/order/${slug}/status/${response.id}`);
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
      <div className="max-w-lg mx-auto px-6 py-8 text-center">
        <p className="text-muted-foreground mb-4">
          Payment session expired. Please try again.
        </p>
        <Button onClick={() => setStep("cart")}>Go Back</Button>
      </div>
    );
  }

  return (
    <div className="max-w-lg mx-auto px-6 py-8">
      <PaymentOverlay visible={isProcessing} />
      <div className="mb-6">
        <p className="text-[11px] uppercase tracking-[3px] text-muted-foreground mb-2">
          Checkout
        </p>
        <h2 className="text-2xl font-semibold text-foreground">Payment</h2>
      </div>

      {/* Order summary card */}
      <div className="glass-card rounded-2xl p-5 mb-6">
        <p className="text-[11px] uppercase tracking-[3px] text-muted-foreground mb-3">
          Order Summary
        </p>
        <div className="space-y-2 mb-4">
          {parsedItems.map((item, index) => (
            <div key={index} className="flex justify-between items-start">
              <div className="flex-1 min-w-0 mr-3">
                <p className="text-foreground text-sm font-medium">{item.name}</p>
                {item.variant.label && (
                  <p className="text-muted-foreground text-xs">{item.variant.label}</p>
                )}
                {item.modifiers.length > 0 && (
                  <div className="mt-0.5">
                    {item.modifiers.map((m) => (
                      <p key={m.id} className="text-muted-foreground text-xs">
                        + {m.name} (+${m.price_adjustment})
                      </p>
                    ))}
                  </div>
                )}
              </div>
              <div className="text-right shrink-0">
                <p className="text-foreground text-sm">×{item.quantity}</p>
                <p className="text-muted-foreground text-xs">${item.line_total}</p>
              </div>
            </div>
          ))}
        </div>
        <div className="border-t border-border/40 pt-3 space-y-1">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Subtotal</span>
            <span className="text-foreground">${subtotal.toFixed(2)}</span>
          </div>
          {parseFloat(taxRate) > 0 && (
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Tax ({taxRate}%)</span>
              <span className="text-muted-foreground">${tax.toFixed(2)}</span>
            </div>
          )}
          <div className="flex justify-between items-center pt-1">
            <span className="text-foreground font-semibold text-sm">Total</span>
            <span className="gradient-text font-bold text-lg">${total.toFixed(2)}</span>
          </div>
        </div>
      </div>

      {hasSavedCards && !useNewCard ? (
        <div className="space-y-4">
          <div className="glass-card rounded-2xl p-5">
            <p className="text-[11px] uppercase tracking-[3px] text-muted-foreground mb-3">
              Saved Cards
            </p>
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
          </div>

          {paymentError && (
            <p className="text-destructive text-sm">{paymentError}</p>
          )}

          <Button
            variant="gradient"
            size="lg"
            className="w-full glow-primary mt-4"
            onClick={handleSavedCardPayment}
            disabled={isProcessing}
          >
            {isProcessing ? "Processing payment..." : "Pay Now"}
          </Button>
        </div>
      ) : clientSecret ? (
        <div>
          {isAuthenticated && (
            <label className="flex items-center gap-2 mb-4 cursor-pointer">
              <input
                type="checkbox"
                checked={saveCard}
                onChange={(e) => setSaveCard(e.target.checked)}
                className="accent-primary"
              />
              <span className="text-sm">Save this card for future orders</span>
            </label>
          )}
          <div className="glass-card rounded-2xl p-6">
            <Elements
              stripe={stripePromise}
              options={{
                clientSecret,
                appearance: stripeAppearance,
              }}
            >
              <PaymentForm saveCard={saveCard} slug={slug} orderId={orderId} />
            </Elements>
          </div>
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
        onClick={() => setStep("cart")}
      >
        Back to order
      </Button>
    </div>
  );
}
