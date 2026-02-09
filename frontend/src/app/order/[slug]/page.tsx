"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useOrderStore } from "@/stores/order-store";
import { fetchMenu } from "@/lib/api";
import { WelcomeStep } from "./components/WelcomeStep";
import { InputStep } from "./components/InputStep";
import { LoadingStep } from "./components/LoadingStep";
import { ConfirmationStep } from "./components/ConfirmationStep";
import { SubmittedStep } from "./components/SubmittedStep";

export default function OrderPage() {
  const params = useParams<{ slug: string }>();
  const slug = params.slug;
  const step = useOrderStore((s) => s.step);
  const reset = useOrderStore((s) => s.reset);
  const [restaurantName, setRestaurantName] = useState("");
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    reset();
    fetchMenu(slug)
      .then((menu) => {
        setRestaurantName(menu.restaurant_name);
        setLoading(false);
      })
      .catch(() => {
        setNotFound(true);
        setLoading(false);
      });
  }, [slug, reset]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (notFound) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-muted-foreground">Restaurant not found.</p>
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-background">
      {step === "welcome" && <WelcomeStep restaurantName={restaurantName} />}
      {step === "input" && <InputStep slug={slug} />}
      {step === "loading" && <LoadingStep />}
      {step === "confirmation" && <ConfirmationStep slug={slug} />}
      {step === "submitted" && <SubmittedStep />}
    </main>
  );
}
