"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Settings } from "lucide-react";
import { useOrderStore } from "@/stores/order-store";
import { useAuthStore } from "@/stores/auth-store";
import { useMenu } from "@/hooks/use-menu";
import { Button } from "@/components/ui/button";
import { PreferencesDialog } from "@/components/PreferencesDialog";
import { WelcomeStep } from "./components/WelcomeStep";
import { OrderingStep } from "./components/OrderingStep";
import { ConfirmationStep } from "./components/ConfirmationStep";
import { PaymentStep } from "./components/PaymentStep";
import { SubmittedStep } from "./components/SubmittedStep";
import TabReviewStep from "./components/TabReviewStep";
import TabStatusBar from "./components/TabStatusBar";
import { TabClosedStep } from "./components/TabClosedStep";

export default function OrderPage() {
  const params = useParams<{ slug: string }>();
  const slug = params.slug;
  const step = useOrderStore((s) => s.step);
  const reset = useOrderStore((s) => s.reset);
  const setPaymentModel = useOrderStore((s) => s.setPaymentModel);
  const { data: menu, isLoading, error } = useMenu(slug);
  const { checkAuth } = useAuthStore();
  const [prefsOpen, setPrefsOpen] = useState(false);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  useEffect(() => {
    reset();
  }, [reset]);

  useEffect(() => {
    if (menu && menu.available !== false && menu.payment_model) {
      setPaymentModel(menu.payment_model);
    }
  }, [menu, setPaymentModel]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (menu && menu.available === false) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen px-4 text-center">
        <h1 className="text-xl font-semibold mb-2">{menu.restaurant_name}</h1>
        <p className="text-muted-foreground">
          This restaurant is not currently accepting online orders.
        </p>
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

  if (!menu.payment_ready) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <div className="text-center px-6 max-w-md">
          <div className="mx-auto mb-6 h-16 w-16 rounded-full bg-muted flex items-center justify-center">
            <Settings className="h-8 w-8 text-muted-foreground" />
          </div>
          <h1 className="text-2xl font-bold mb-2">Restaurant Setup in Progress</h1>
          <p className="text-muted-foreground">
            {menu.restaurant_name} is still setting up their ordering system. Please check back soon.
          </p>
        </div>
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-background">
      <div className="fixed top-4 right-4 z-40 flex items-center gap-2">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setPrefsOpen(true)}
          title="Preferences"
        >
          <Settings className="h-5 w-5" />
        </Button>
      </div>
      <TabStatusBar />
      {step === "welcome" && (
        <WelcomeStep
          restaurantName={menu.restaurant_name}
          slug={slug}
          operatingHours={menu.operating_hours}
          holidayOverrides={menu.holiday_overrides}
          acceptingOrders={menu.accepting_orders}
        />
      )}
      {step === "ordering" && <OrderingStep slug={slug} categories={menu.categories} taxRate={menu.tax_rate} />}
      {step === "cart" && <ConfirmationStep slug={slug} taxRate={menu.tax_rate} paymentMode={menu.payment_mode ?? "stripe"} />}
      {step === "payment" && <PaymentStep taxRate={menu.tax_rate} />}
      {step === "submitted" && <SubmittedStep slug={slug} />}
      {step === "tab_review" && <TabReviewStep slug={slug} />}
      {step === "tab_closed" && <TabClosedStep />}

      <PreferencesDialog open={prefsOpen} onOpenChange={setPrefsOpen} />
    </main>
  );
}
