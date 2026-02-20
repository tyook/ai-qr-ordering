# Saved Payment Methods Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow logged-in customers to save payment methods at checkout and reuse them for future orders.

**Architecture:** Add `stripe_customer_id` to Customer model. Stripe stores all card data — we only hold a reference. PaymentIntent creation is extended with optional `payment_method_id` (charge saved card server-side) and `save_card` flag (attach card after payment). Two new customer endpoints for listing/deleting saved cards. Frontend PaymentStep shows saved card picker when logged in.

**Tech Stack:** Django, Stripe Python SDK, Next.js, @stripe/react-stripe-js, Zustand, React Query

---

### Task 1: Add `stripe_customer_id` to Customer model

**Files:**
- Modify: `backend/customers/models.py:6-34`

**Step 1: Add the field**

In `backend/customers/models.py`, add after `auth_provider_id` (line 20):

```python
stripe_customer_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
```

**Step 2: Create and run migration**

```bash
cd /Users/k.yook/projects/ai-qr-ordering/backend
POSTGRES_HOST=localhost python manage.py makemigrations customers
POSTGRES_HOST=localhost python manage.py migrate
```

Expected: Migration creates successfully and applies.

**Step 3: Commit**

```bash
git add backend/customers/
git commit -m "feat: add stripe_customer_id to Customer model"
```

---

### Task 2: Add `stripe_payment_method_id` to Order model

**Files:**
- Modify: `backend/orders/models.py:40-53`

**Step 1: Add the field**

In `backend/orders/models.py`, add after `stripe_payment_intent_id` (line 53):

```python
stripe_payment_method_id = models.CharField(
    max_length=255, blank=True, null=True,
)
```

**Step 2: Create and run migration**

```bash
cd /Users/k.yook/projects/ai-qr-ordering/backend
POSTGRES_HOST=localhost python manage.py makemigrations orders
POSTGRES_HOST=localhost python manage.py migrate
```

**Step 3: Commit**

```bash
git add backend/orders/
git commit -m "feat: add stripe_payment_method_id to Order model"
```

---

### Task 3: Add helper to get or create Stripe Customer

**Files:**
- Modify: `backend/customers/models.py`

**Step 1: Add method to Customer model**

Add this method to the `Customer` class in `backend/customers/models.py`:

```python
def get_or_create_stripe_customer(self):
    """Get existing or create new Stripe Customer. Returns stripe_customer_id."""
    if self.stripe_customer_id:
        return self.stripe_customer_id

    import stripe
    from django.conf import settings
    stripe.api_key = settings.STRIPE_SECRET_KEY

    stripe_customer = stripe.Customer.create(
        email=self.email,
        name=self.name,
        metadata={"customer_id": str(self.id)},
    )
    self.stripe_customer_id = stripe_customer.id
    self.save(update_fields=["stripe_customer_id"])
    return self.stripe_customer_id
```

**Step 2: Commit**

```bash
git add backend/customers/models.py
git commit -m "feat: add get_or_create_stripe_customer helper"
```

---

### Task 4: Modify create-payment endpoint to support saved cards and save_card flag

**Files:**
- Modify: `backend/orders/views.py:315-348`

**Step 1: Update the PaymentIntent creation block**

Replace lines 315-348 in `backend/orders/views.py` (the Stripe PaymentIntent section) with:

```python
        # Create Stripe PaymentIntent
        if not settings.STRIPE_SECRET_KEY:
            order.delete()
            return Response(
                {"detail": "Payment system not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        stripe.api_key = settings.STRIPE_SECRET_KEY
        amount_cents = int((grand_total * Decimal("100")).quantize(Decimal("1")))

        payment_method_id = data.get("payment_method_id")
        save_card = data.get("save_card", False)

        intent_params = {
            "amount": amount_cents,
            "currency": restaurant.currency.lower(),
            "automatic_payment_methods": {"enabled": True},
            "metadata": {
                "order_id": str(order.id),
                "restaurant_slug": restaurant.slug,
            },
        }

        # If customer is logged in, attach Stripe Customer
        if customer:
            stripe_customer_id = customer.get_or_create_stripe_customer()
            intent_params["customer"] = stripe_customer_id

            if save_card:
                intent_params["setup_future_usage"] = "on_session"

        # If using a saved payment method, confirm immediately server-side
        if payment_method_id and customer:
            intent_params["payment_method"] = payment_method_id
            intent_params["confirm"] = True
            intent_params["return_url"] = data.get("return_url", "https://localhost")

        try:
            intent = stripe.PaymentIntent.create(**intent_params)
        except stripe.error.StripeError as e:
            order.delete()
            return Response(
                {"detail": f"Payment setup failed: {str(e)}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        order.stripe_payment_intent_id = intent.id
        if payment_method_id:
            order.stripe_payment_method_id = payment_method_id
        order.save(update_fields=["stripe_payment_intent_id", "stripe_payment_method_id"])

        response_data = OrderResponseSerializer(order).data
        response_data["client_secret"] = intent.client_secret

        # If payment was confirmed server-side and succeeded
        if intent.status == "succeeded":
            order.status = "confirmed"
            order.payment_status = "paid"
            order.save(update_fields=["status", "payment_status"])
            response_data["status"] = "confirmed"
            response_data["payment_status"] = "paid"

        return Response(response_data, status=status.HTTP_201_CREATED)
```

**Step 2: Add `save_card` and `payment_method_id` to the serializer**

In `backend/orders/serializers.py`, add to `ConfirmOrderSerializer` (after line 26):

```python
payment_method_id = serializers.CharField(required=False, default="", allow_blank=True)
save_card = serializers.BooleanField(required=False, default=False)
return_url = serializers.URLField(required=False, default="")
```

**Step 3: Run existing tests to make sure nothing is broken**

```bash
cd /Users/k.yook/projects/ai-qr-ordering/backend
pytest orders/tests/test_api_orders.py -v
```

Expected: All existing tests pass (they don't send `payment_method_id` or `save_card` so the default behavior is unchanged).

**Step 4: Commit**

```bash
git add backend/orders/
git commit -m "feat: support saved cards and save_card flag in create-payment"
```

---

### Task 5: Add payment methods list and delete endpoints

**Files:**
- Modify: `backend/customers/views.py`
- Modify: `backend/customers/urls.py`

**Step 1: Add PaymentMethodsView to customers/views.py**

Add at the end of `backend/customers/views.py`:

```python
import stripe as stripe_lib

class PaymentMethodsView(CustomerAuthMixin, APIView):
    """GET: list saved payment methods. DELETE: detach a payment method."""
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        customer = self.get_customer(request)
        if not customer:
            return Response(
                {"detail": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not customer.stripe_customer_id:
            return Response([])

        from django.conf import settings
        stripe_lib.api_key = settings.STRIPE_SECRET_KEY

        try:
            methods = stripe_lib.PaymentMethod.list(
                customer=customer.stripe_customer_id,
                type="card",
            )
        except stripe_lib.error.StripeError:
            return Response([])

        result = []
        for pm in methods.data:
            result.append({
                "id": pm.id,
                "brand": pm.card.brand,
                "last4": pm.card.last4,
                "exp_month": pm.card.exp_month,
                "exp_year": pm.card.exp_year,
            })

        return Response(result)


class PaymentMethodDetailView(CustomerAuthMixin, APIView):
    """DELETE: detach a specific payment method."""
    authentication_classes = []
    permission_classes = []

    def delete(self, request, pm_id):
        customer = self.get_customer(request)
        if not customer:
            return Response(
                {"detail": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not customer.stripe_customer_id:
            return Response(
                {"detail": "No payment methods found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        from django.conf import settings
        stripe_lib.api_key = settings.STRIPE_SECRET_KEY

        try:
            # Verify the payment method belongs to this customer
            pm = stripe_lib.PaymentMethod.retrieve(pm_id)
            if pm.customer != customer.stripe_customer_id:
                return Response(
                    {"detail": "Payment method not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            stripe_lib.PaymentMethod.detach(pm_id)
        except stripe_lib.error.StripeError as e:
            return Response(
                {"detail": f"Failed to remove payment method: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)
```

**Step 2: Add URL routes**

In `backend/customers/urls.py`, add imports and paths:

Add to imports:
```python
from customers.views import (
    CustomerRegisterView,
    CustomerLoginView,
    GoogleAuthView,
    AppleAuthView,
    CustomerTokenRefreshView,
    CustomerProfileView,
    CustomerOrderHistoryView,
    PaymentMethodsView,
    PaymentMethodDetailView,
)
```

Add to urlpatterns:
```python
path("payment-methods/", PaymentMethodsView.as_view(), name="customer-payment-methods"),
path("payment-methods/<str:pm_id>/", PaymentMethodDetailView.as_view(), name="customer-payment-method-detail"),
```

**Step 3: Commit**

```bash
git add backend/customers/
git commit -m "feat: add payment methods list and delete endpoints"
```

---

### Task 6: Add frontend types and API functions

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/lib/api.ts`

**Step 1: Add SavedPaymentMethod type**

In `frontend/src/types/index.ts`, add at the end:

```typescript
export interface SavedPaymentMethod {
  id: string;
  brand: string;
  last4: string;
  exp_month: number;
  exp_year: number;
}
```

**Step 2: Update CreatePaymentResponse**

In `frontend/src/types/index.ts`, update `CreatePaymentResponse`:

```typescript
export interface CreatePaymentResponse extends OrderResponse {
  client_secret: string;
}
```

No change needed — `client_secret` is already there and the status/payment_status fields come from OrderResponse.

**Step 3: Add API functions**

In `frontend/src/lib/api.ts`, add these functions:

```typescript
export async function fetchPaymentMethods(): Promise<SavedPaymentMethod[]> {
  return customerApiFetch<SavedPaymentMethod[]>("/api/customer/payment-methods/");
}

export async function deletePaymentMethod(pmId: string): Promise<void> {
  await customerApiFetch<void>(`/api/customer/payment-methods/${pmId}/`, {
    method: "DELETE",
  });
}
```

Add `SavedPaymentMethod` to the import block from `@/types` at the top of api.ts (line 85-94).

**Step 4: Update `createPayment` to accept optional saved card params**

In `frontend/src/lib/api.ts`, update the `createPayment` function:

```typescript
export async function createPayment(
  slug: string,
  items: ConfirmOrderItem[],
  rawInput: string,
  tableIdentifier: string,
  language: string,
  customerName?: string,
  customerPhone?: string,
  paymentMethodId?: string,
  saveCard?: boolean,
): Promise<CreatePaymentResponse> {
  return customerApiFetch<CreatePaymentResponse>(`/api/order/${slug}/create-payment/`, {
    method: "POST",
    body: JSON.stringify({
      items,
      raw_input: rawInput,
      table_identifier: tableIdentifier,
      language,
      customer_name: customerName || "",
      customer_phone: customerPhone || "",
      payment_method_id: paymentMethodId || "",
      save_card: saveCard || false,
      return_url: window.location.href,
    }),
  });
}
```

Note: `createPayment` now uses `customerApiFetch` instead of `apiFetch` so the customer JWT is sent along (needed for the backend to identify the customer and attach the Stripe Customer).

**Step 5: Commit**

```bash
git add frontend/src/types/ frontend/src/lib/api.ts
git commit -m "feat: add payment methods types and API functions"
```

---

### Task 7: Add React Query hooks for payment methods

**Files:**
- Create: `frontend/src/hooks/use-payment-methods.ts`

**Step 1: Create the hooks file**

Create `frontend/src/hooks/use-payment-methods.ts`:

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchPaymentMethods, deletePaymentMethod } from "@/lib/api";

export function usePaymentMethods() {
  return useQuery({
    queryKey: ["payment-methods"],
    queryFn: fetchPaymentMethods,
  });
}

export function useDeletePaymentMethod() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deletePaymentMethod,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["payment-methods"] });
    },
  });
}
```

**Step 2: Commit**

```bash
git add frontend/src/hooks/use-payment-methods.ts
git commit -m "feat: add usePaymentMethods and useDeletePaymentMethod hooks"
```

---

### Task 8: Update PaymentStep to show saved cards

**Files:**
- Modify: `frontend/src/app/order/[slug]/components/PaymentStep.tsx`

**Step 1: Rewrite PaymentStep**

Replace the entire file with:

```tsx
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

function PaymentForm({ saveCard }: { saveCard: boolean }) {
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
            <PaymentForm saveCard={saveCard} />
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
```

**Step 2: Commit**

```bash
git add frontend/src/app/order/[slug]/components/PaymentStep.tsx
git commit -m "feat: show saved cards in PaymentStep with save card option"
```

---

### Task 9: Wire save_card flag into the confirmation step's create-payment call

**Files:**
- Modify: The component that calls `createPayment` from the confirmation step (need to check how it's invoked)

**Step 1: Find and update the confirmation step**

The confirmation step currently calls `createPayment` without `paymentMethodId` or `saveCard`. Since `saveCard` is handled in the PaymentStep via `setup_future_usage` on the PaymentIntent, the confirmation step's call to `createPayment` needs to pass through to `customerApiFetch` so the customer JWT is sent.

Update the call site to use the updated `createPayment` signature (the new optional params default to `undefined` so no change needed at the call site — just ensure `createPayment` uses `customerApiFetch`).

This was already handled in Task 6. Verify it works.

**Step 2: Commit (if any changes needed)**

---

### Task 10: Add Payment Methods management page

**Files:**
- Create: `frontend/src/app/account/payment-methods/page.tsx`

**Step 1: Create the page**

Create `frontend/src/app/account/payment-methods/page.tsx`:

```tsx
"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useCustomerAuthStore } from "@/stores/customer-auth-store";
import { usePaymentMethods, useDeletePaymentMethod } from "@/hooks/use-payment-methods";

export default function PaymentMethodsPage() {
  const router = useRouter();
  const { isAuthenticated, checkAuth } = useCustomerAuthStore();
  const { data: methods, isLoading, error } = usePaymentMethods();
  const deleteMutation = useDeletePaymentMethod();

  useEffect(() => {
    if (!checkAuth()) {
      router.push("/account/login");
    }
  }, [checkAuth, router]);

  if (!isAuthenticated) {
    return null;
  }

  if (isLoading) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-8 text-center">
        <p className="text-destructive">Failed to load payment methods.</p>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">Payment Methods</h1>
      {!methods || methods.length === 0 ? (
        <Card className="p-8 text-center">
          <p className="text-muted-foreground">No saved payment methods.</p>
          <p className="text-sm text-muted-foreground mt-2">
            You can save a card during checkout for faster future payments.
          </p>
        </Card>
      ) : (
        <div className="space-y-3">
          {methods.map((method) => (
            <Card key={method.id} className="p-4 flex items-center justify-between">
              <div>
                <span className="font-medium capitalize">{method.brand}</span>
                <span className="text-muted-foreground"> ending in {method.last4}</span>
                <p className="text-sm text-muted-foreground mt-1">
                  Expires {String(method.exp_month).padStart(2, "0")}/{method.exp_year}
                </p>
              </div>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => deleteMutation.mutate(method.id)}
                disabled={deleteMutation.isPending}
              >
                {deleteMutation.isPending ? "Removing..." : "Remove"}
              </Button>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/app/account/payment-methods/
git commit -m "feat: add payment methods management page"
```

---

### Task 11: Run full test suite and verify

**Step 1: Run backend tests**

```bash
cd /Users/k.yook/projects/ai-qr-ordering/backend
pytest orders/tests/test_api_orders.py -v
```

Expected: All existing tests pass.

**Step 2: Build frontend**

```bash
cd /Users/k.yook/projects/ai-qr-ordering/frontend
npm run build
```

Expected: Build succeeds with no type errors.

**Step 3: Fix any issues found**

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: saved payment methods — complete implementation"
```
