"use client";

import { Button } from "@/components/ui/button";
import { useOrderStore } from "@/stores/order-store";

interface WelcomeStepProps {
  restaurantName: string;
}

export function WelcomeStep({ restaurantName }: WelcomeStepProps) {
  const setStep = useOrderStore((s) => s.setStep);

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
      <h1 className="text-3xl font-bold mb-2">{restaurantName}</h1>
      <p className="text-muted-foreground mb-8">
        Type or speak your order in any language
      </p>
      <Button size="lg" onClick={() => setStep("input")}>
        Start Ordering
      </Button>
    </div>
  );
}
