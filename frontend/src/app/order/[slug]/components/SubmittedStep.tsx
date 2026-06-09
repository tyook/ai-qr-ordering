"use client";

import { useState } from "react";
import { CheckCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { SocialLoginButtons } from "@/components/SocialLoginButtons";
import { useOrderStore } from "@/stores/order-store";
import { useAuthStore } from "@/stores/auth-store";
import { OrderTracker } from "./OrderTracker";

interface SubmittedStepProps {
  slug: string;
}

export function SubmittedStep({ slug }: SubmittedStepProps) {
  const { orderId, tableIdentifier, customerName, customerPhone, paymentMode, parsedItems, reset, paymentModel, setStep } = useOrderStore();
  const { isAuthenticated, register } = useAuthStore();

  const [showRegister, setShowRegister] = useState(false);
  const [registerForm, setRegisterForm] = useState({ email: "", password: "" });
  const [registerError, setRegisterError] = useState("");
  const [registerLoading, setRegisterLoading] = useState(false);
  const [registerSuccess, setRegisterSuccess] = useState(false);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setRegisterLoading(true);
    setRegisterError("");
    try {
      await register({
        email: registerForm.email,
        password: registerForm.password,
        name: customerName,
        phone: customerPhone,
        link_order_id: orderId || undefined,
      });
      setRegisterSuccess(true);
      setShowRegister(false);
    } catch (err) {
      setRegisterError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setRegisterLoading(false);
    }
  };

  return (
    <div className="relative min-h-[calc(100vh-4rem)] flex flex-col items-center justify-center px-6 text-center">
      {/* Ambient success glow */}
      <div
        aria-hidden
        className="absolute w-[250px] h-[250px] bg-[radial-gradient(circle,rgba(34,197,94,0.12),transparent_70%)] rounded-full pointer-events-none"
      />

      {/* Success icon */}
      <div className="w-20 h-20 bg-green-500/10 border border-green-500/20 rounded-full flex items-center justify-center mb-6">
        <CheckCircle className="text-green-400 w-10 h-10" />
      </div>

      <h2 className="text-2xl font-bold text-foreground mb-2">Order Submitted</h2>

      {orderId && (
        <p className="gradient-text text-lg font-semibold">
          #{orderId.slice(0, 8)}
        </p>
      )}

      {tableIdentifier && (
        <p className="text-muted-foreground text-sm mt-1">Table {tableIdentifier}</p>
      )}

      <p className="text-muted-foreground text-sm mt-2 max-w-xs">
        Your order has been sent to the kitchen.
        {paymentMode === "pos_collected" && (
          <span className="block mt-1 font-medium text-foreground">
            Please pay at the counter.
          </span>
        )}
      </p>

      {/* Order details card */}
      {parsedItems && parsedItems.length > 0 && (
        <div className="glass-card rounded-2xl p-5 mt-8 w-full max-w-sm text-left">
          <p className="text-[11px] uppercase tracking-[3px] text-muted-foreground mb-3">
            Your Items
          </p>
          <div className="space-y-2">
            {parsedItems.map((item, index) => (
              <div key={index}>
                <div className="flex justify-between items-center">
                  <span className="text-foreground/80 text-sm">
                    {item.quantity > 1 && (
                      <span className="text-muted-foreground text-xs mr-1">×{item.quantity}</span>
                    )}
                    {item.name}
                  </span>
                  <span className="text-muted-foreground text-xs">${item.line_total}</span>
                </div>
                {item.modifiers.length > 0 && (
                  <div className="ml-4 mt-0.5">
                    {item.modifiers.map((m) => (
                      <p key={m.id} className="text-muted-foreground text-xs">
                        + {m.name} (+${m.price_adjustment})
                      </p>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {orderId && (
        <div className="w-full max-w-sm mt-6">
          <OrderTracker slug={slug} orderId={orderId} />
        </div>
      )}

      {/* Account creation prompt */}
      {!isAuthenticated && !registerSuccess && (
        <div className="glass-card rounded-2xl p-6 mt-6 w-full max-w-sm text-left">
          <h3 className="text-lg font-semibold text-foreground mb-2">Save your order to an account?</h3>
          <p className="text-sm text-muted-foreground mb-4">
            Create an account to track this order and save your preferences for next time.
          </p>

          {!showRegister ? (
            <div className="space-y-3">
              <SocialLoginButtons
                linkOrderId={orderId || undefined}
                onSuccess={() => setRegisterSuccess(true)}
                onError={(err) => setRegisterError(err)}
              />
              {registerError && (
                <p className="text-destructive text-sm">{registerError}</p>
              )}
              <div className="relative my-2">
                <div className="absolute inset-0 flex items-center">
                  <Separator className="w-full" />
                </div>
                <div className="relative flex justify-center text-xs uppercase">
                  <span className="bg-card px-2 text-muted-foreground">or</span>
                </div>
              </div>
              <Button variant="outline" className="w-full" onClick={() => setShowRegister(true)}>
                Sign up with email
              </Button>
            </div>
          ) : (
            <form onSubmit={handleRegister} className="space-y-3">
              <div>
                <Label htmlFor="register-email">Email</Label>
                <Input
                  id="register-email"
                  type="email"
                  value={registerForm.email}
                  onChange={(e) => setRegisterForm({ ...registerForm, email: e.target.value })}
                  required
                />
              </div>
              <div>
                <Label htmlFor="register-password">Password (min. 8 characters)</Label>
                <Input
                  id="register-password"
                  type="password"
                  value={registerForm.password}
                  onChange={(e) => setRegisterForm({ ...registerForm, password: e.target.value })}
                  required
                  minLength={8}
                />
              </div>
              {registerError && (
                <p className="text-destructive text-sm">{registerError}</p>
              )}
              <div className="flex gap-2">
                <Button type="submit" variant="gradient" className="flex-1" disabled={registerLoading}>
                  {registerLoading ? "Creating account..." : "Create Account"}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setShowRegister(false);
                    setRegisterError("");
                  }}
                >
                  Cancel
                </Button>
              </div>
            </form>
          )}
        </div>
      )}

      {/* Success message after registration */}
      {registerSuccess && (
        <div className="glass-card rounded-2xl p-6 mt-6 w-full max-w-sm text-center">
          <div className="w-12 h-12 bg-green-500/10 border border-green-500/20 rounded-full flex items-center justify-center mx-auto mb-3">
            <CheckCircle className="text-green-400 w-6 h-6" />
          </div>
          <h3 className="text-lg font-semibold text-foreground mb-1">Account created!</h3>
          <p className="text-sm text-muted-foreground">
            Your order has been linked to your new account. You can now track all your orders.
          </p>
        </div>
      )}

      {paymentModel === "tab" && (
        <div className="flex flex-col gap-3 mt-6 w-full max-w-sm">
          <Button
            variant="outline"
            size="lg"
            className="w-full"
            onClick={() => {
              useOrderStore.setState({ parsedItems: [], parsedAllergies: [], totalPrice: "0.00", rawInput: "" });
              setStep("ordering");
            }}
          >
            Order More
          </Button>
          <Button
            variant="gradient"
            size="lg"
            className="w-full"
            onClick={() => setStep("tab_review")}
          >
            View Tab &amp; Pay
          </Button>
        </div>
      )}

      {paymentModel !== "tab" && (
        <Button
          variant="gradient"
          size="lg"
          className="mt-6 w-full max-w-sm"
          onClick={reset}
        >
          Done
        </Button>
      )}
    </div>
  );
}
