"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useRequireRestaurantAccess } from "@/hooks/use-auth";
import {
  useSubscription,
  useCreateCheckout,
  useCreateBillingPortal,
  useCancelSubscription,
  useReactivateSubscription,
} from "@/hooks/use-subscription";

const PLANS = [
  {
    id: "starter",
    name: "Starter",
    monthlyPrice: 49,
    annualPrice: 40,
    orderLimit: 200,
    overage: "$0.20",
    description: "For small cafes (~7 orders/day)",
  },
  {
    id: "growth",
    name: "Growth",
    monthlyPrice: 99,
    annualPrice: 82,
    orderLimit: 600,
    overage: "$0.15",
    description: "For typical independents (~20 orders/day)",
  },
  {
    id: "pro",
    name: "Pro",
    monthlyPrice: 199,
    annualPrice: 166,
    orderLimit: 1500,
    overage: "$0.10",
    description: "For busy restaurants (~50 orders/day)",
  },
];

function StatusBadge({ status }: { status: string }) {
  const variant =
    status === "active"
      ? "default"
      : status === "trialing"
        ? "secondary"
        : status === "past_due"
          ? "destructive"
          : "outline";

  return <Badge variant={variant}>{status.replace("_", " ")}</Badge>;
}

export default function BillingPage() {
  const params = useParams<{ slug: string }>();
  const isAuthenticated = useRequireRestaurantAccess();
  const { data: subscription, isLoading } = useSubscription(params.slug);
  const createCheckout = useCreateCheckout(params.slug);
  const createPortal = useCreateBillingPortal(params.slug);
  const cancelSub = useCancelSubscription(params.slug);
  const reactivateSub = useReactivateSubscription(params.slug);

  if (isAuthenticated === null || isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (isAuthenticated === false) {
    return null;
  }

  const usagePercent = subscription
    ? Math.round((subscription.order_count / subscription.order_limit) * 100)
    : 0;

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-4xl mx-auto">
        <Link
          href="/account/restaurants"
          className="text-sm text-muted-foreground hover:underline"
        >
          Back to dashboard
        </Link>
        <h1 className="text-2xl font-bold mb-6">Billing & Subscription</h1>

        {/* Current Plan */}
        {subscription && (
          <Card className="p-6 mb-6">
            <div className="flex justify-between items-start mb-4">
              <div>
                <h2 className="text-lg font-semibold">Current Plan</h2>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-2xl font-bold">
                    {subscription.plan_name}
                  </span>
                  <StatusBadge status={subscription.status} />
                  {subscription.cancel_at_period_end && (
                    <Badge variant="outline">Cancels at period end</Badge>
                  )}
                </div>
              </div>
              <div className="flex gap-2">
                {subscription.status !== "trialing" &&
                  subscription.is_active && (
                    <Button
                      variant="outline"
                      onClick={() => createPortal.mutate()}
                      disabled={createPortal.isPending}
                    >
                      {createPortal.isPending ? "Loading..." : "Manage Billing"}
                    </Button>
                  )}
                {subscription.status !== "trialing" &&
                  subscription.is_active &&
                  !subscription.cancel_at_period_end && (
                    <Button
                      variant="destructive"
                      onClick={() => {
                        if (
                          confirm(
                            "Cancel your subscription? You'll retain access until the end of your billing period."
                          )
                        ) {
                          cancelSub.mutate();
                        }
                      }}
                      disabled={cancelSub.isPending}
                    >
                      {cancelSub.isPending
                        ? "Canceling..."
                        : "Cancel Subscription"}
                    </Button>
                  )}
                {subscription.cancel_at_period_end && (
                  <Button
                    variant="default"
                    onClick={() => reactivateSub.mutate()}
                    disabled={reactivateSub.isPending}
                  >
                    {reactivateSub.isPending
                      ? "Reactivating..."
                      : "Reactivate Subscription"}
                  </Button>
                )}
              </div>
            </div>

            {/* Usage */}
            <div className="mt-4">
              <div className="flex justify-between text-sm mb-1">
                <span>
                  Orders this period: {subscription.order_count} /{" "}
                  {subscription.order_limit}
                </span>
                <span>{usagePercent}%</span>
              </div>
              <div className="w-full bg-muted rounded-full h-2">
                <div
                  className={`h-2 rounded-full transition-all ${
                    usagePercent >= 100
                      ? "bg-destructive"
                      : usagePercent >= 80
                        ? "bg-yellow-500"
                        : "bg-primary"
                  }`}
                  style={{ width: `${Math.min(usagePercent, 100)}%` }}
                />
              </div>
              {subscription.overage_count > 0 && (
                <p className="text-sm text-muted-foreground mt-1">
                  {subscription.overage_count} overage orders this period
                </p>
              )}
            </div>

            {/* Trial info */}
            {subscription.status === "trialing" && subscription.trial_end && (
              <p className="text-sm text-muted-foreground mt-4">
                Trial ends:{" "}
                {new Date(subscription.trial_end).toLocaleDateString()}
              </p>
            )}

            {/* Period info */}
            {subscription.current_period_end &&
              subscription.status !== "trialing" && (
                <p className="text-sm text-muted-foreground mt-2">
                  Current period ends:{" "}
                  {new Date(
                    subscription.current_period_end
                  ).toLocaleDateString()}
                </p>
              )}
          </Card>
        )}

        {/* Plan Selection */}
        <h2 className="text-lg font-semibold mb-4">
          {subscription?.status === "trialing" ||
          subscription?.status === "canceled"
            ? "Choose a Plan"
            : "Change Plan"}
        </h2>
        <div className="grid md:grid-cols-3 gap-4">
          {PLANS.map((plan) => {
            const isCurrent =
              subscription?.plan === plan.id && subscription?.is_active;
            return (
              <Card
                key={plan.id}
                className={`p-6 ${isCurrent ? "border-primary border-2" : ""}`}
              >
                <h3 className="text-lg font-semibold">{plan.name}</h3>
                <p className="text-sm text-muted-foreground mb-3">
                  {plan.description}
                </p>
                <div className="mb-4">
                  <span className="text-3xl font-bold">
                    ${plan.monthlyPrice}
                  </span>
                  <span className="text-muted-foreground">/mo</span>
                  <p className="text-xs text-muted-foreground mt-1">
                    or ${plan.annualPrice}/mo billed annually
                  </p>
                </div>
                <ul className="text-sm space-y-1 mb-4">
                  <li>{plan.orderLimit.toLocaleString()} orders/month</li>
                  <li>{plan.overage}/order overage</li>
                  <li>All features included</li>
                </ul>
                {isCurrent ? (
                  <Button variant="outline" className="w-full" disabled>
                    Current Plan
                  </Button>
                ) : (
                  <div className="space-y-2">
                    <Button
                      className="w-full"
                      onClick={() =>
                        createCheckout.mutate({
                          plan: plan.id,
                          interval: "monthly",
                        })
                      }
                      disabled={createCheckout.isPending}
                    >
                      {createCheckout.isPending
                        ? "Loading..."
                        : `$${plan.monthlyPrice}/mo`}
                    </Button>
                    <Button
                      variant="outline"
                      className="w-full"
                      onClick={() =>
                        createCheckout.mutate({
                          plan: plan.id,
                          interval: "annual",
                        })
                      }
                      disabled={createCheckout.isPending}
                    >
                      {createCheckout.isPending
                        ? "Loading..."
                        : `$${plan.annualPrice}/mo annual`}
                    </Button>
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
}
