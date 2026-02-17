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

const stripePromise = loadStripe(
  process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY || ""
);

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
      // Payment succeeded — transition to submitted
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
  const { clientSecret, totalPrice, setStep } = useOrderStore();

  if (!clientSecret) {
    return (
      <div className="max-w-lg mx-auto px-4 py-8 text-center">
        <p className="text-muted-foreground mb-4">
          Payment session expired. Please try again.
        </p>
        <Button onClick={() => setStep("confirmation")}>Go Back</Button>
      </div>
    );
  }

  const subtotal = parseFloat(totalPrice);
  const tax = subtotal * parseFloat(taxRate) / 100;
  const total = subtotal + tax;

  return (
    <div className="max-w-lg mx-auto px-4 py-8">
      <h2 className="text-xl font-semibold mb-2">Payment</h2>
      <p className="text-muted-foreground mb-6">
        Total: ${total.toFixed(2)}
      </p>

      <Elements
        stripe={stripePromise}
        options={{
          clientSecret,
          appearance: { theme: "stripe" },
        }}
      >
        <PaymentForm />
      </Elements>

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
