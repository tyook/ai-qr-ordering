"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Settings } from "lucide-react";
import { useOrderStore } from "@/stores/order-store";
import { useMenu } from "@/hooks/use-menu";
import { Button } from "@/components/ui/button";
import { PreferencesDialog } from "@/components/PreferencesDialog";
import { WelcomeStep } from "./components/WelcomeStep";
import { InputStep } from "./components/InputStep";
import { LoadingStep } from "./components/LoadingStep";
import { ConfirmationStep } from "./components/ConfirmationStep";
import { PaymentStep } from "./components/PaymentStep";
import { SubmittedStep } from "./components/SubmittedStep";
import { MenuModal } from "./components/MenuModal";

export default function OrderPage() {
  const params = useParams<{ slug: string }>();
  const slug = params.slug;
  const step = useOrderStore((s) => s.step);
  const reset = useOrderStore((s) => s.reset);
  const { data: menu, isLoading, error } = useMenu(slug);
  const [prefsOpen, setPrefsOpen] = useState(false);

  useEffect(() => {
    reset();
  }, [reset]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (error || !menu) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-muted-foreground">Restaurant not found.</p>
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-background">
      <div className="fixed top-4 right-4 z-40 flex items-center gap-2">
        <Link href="/account/login" className="text-sm text-muted-foreground hover:text-foreground">
          Sign in
        </Link>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setPrefsOpen(true)}
          title="Preferences"
        >
          <Settings className="h-5 w-5" />
        </Button>
        <MenuModal categories={menu.categories} />
      </div>
      {step === "welcome" && <WelcomeStep restaurantName={menu.restaurant_name} />}
      {step === "input" && <InputStep slug={slug} />}
      {step === "loading" && <LoadingStep />}
      {step === "confirmation" && <ConfirmationStep slug={slug} taxRate={menu.tax_rate} />}
      {step === "payment" && <PaymentStep taxRate={menu.tax_rate} />}
      {step === "submitted" && <SubmittedStep />}

      <PreferencesDialog open={prefsOpen} onOpenChange={setPrefsOpen} />
    </main>
  );
}
