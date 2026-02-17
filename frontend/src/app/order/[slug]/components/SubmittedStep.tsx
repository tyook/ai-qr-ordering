"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { SocialLoginButtons } from "@/components/SocialLoginButtons";
import { useOrderStore } from "@/stores/order-store";
import { useCustomerAuthStore } from "@/stores/customer-auth-store";

export function SubmittedStep() {
  const { orderId, tableIdentifier, customerName, customerPhone } = useOrderStore();
  const { isAuthenticated, register } = useCustomerAuthStore();

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
    <div className="max-w-lg mx-auto px-4 py-8">
      <div className="flex flex-col items-center justify-center text-center mb-8">
        <div className="text-4xl mb-4">&#10003;</div>
        <h2 className="text-2xl font-bold mb-2">Order Placed!</h2>
        {orderId && (
          <p className="text-muted-foreground mb-1">
            Order #{orderId.slice(0, 8)}
          </p>
        )}
        {tableIdentifier && (
          <p className="text-muted-foreground">Table {tableIdentifier}</p>
        )}
        <p className="text-sm text-muted-foreground mt-4">
          Your order has been sent to the kitchen.
        </p>
      </div>

      {/* Account creation prompt */}
      {!isAuthenticated && !registerSuccess && (
        <Card className="p-6">
          <h3 className="text-lg font-semibold mb-2">Save your order to an account?</h3>
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
                <Button type="submit" className="flex-1" disabled={registerLoading}>
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
        </Card>
      )}

      {/* Success message after registration */}
      {registerSuccess && (
        <Card className="p-6 text-center">
          <div className="text-3xl mb-2">&#127881;</div>
          <h3 className="text-lg font-semibold mb-1">Account created!</h3>
          <p className="text-sm text-muted-foreground">
            Your order has been linked to your new account. You can now track all your orders.
          </p>
        </Card>
      )}
    </div>
  );
}
