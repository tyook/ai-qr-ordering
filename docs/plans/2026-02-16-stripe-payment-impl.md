# Stripe Payment Integration — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add pay-at-order Stripe payment so customers must pay before orders reach the kitchen.

**Architecture:** New `create-payment` endpoint replaces `confirm`. It creates an Order (status `pending_payment`) and a Stripe PaymentIntent, returning a `client_secret`. The frontend renders Stripe's `<PaymentElement>` in a new `payment` step. A Stripe webhook confirms payment, transitions the order to `confirmed`, and broadcasts to the kitchen.

**Tech Stack:** Stripe Python SDK (backend), `@stripe/react-stripe-js` + `@stripe/stripe-js` (frontend), Django REST Framework, Next.js 14, Zustand, React Query.

---

### Task 1: Add `stripe` dependency to backend

**Files:**
- Modify: `backend/pyproject.toml`

**Step 1: Add stripe to dependencies**

```bash
cd /Users/k.yook/projects/ai-qr-ordering/backend && poetry add stripe
```

**Step 2: Verify installation**

```bash
cd /Users/k.yook/projects/ai-qr-ordering/backend && poetry run python -c "import stripe; print(stripe.VERSION)"
```

Expected: Prints a version like `11.x.x`

**Step 3: Commit**

```bash
git add backend/pyproject.toml backend/poetry.lock
git commit -m "chore: add stripe Python SDK"
```

---

### Task 2: Add Stripe env vars to Django settings

**Files:**
- Modify: `backend/config/settings.py` (add after line 122, after CHANNEL_LAYERS block)

**Step 1: Add Stripe settings**

Add the following after the `CHANNEL_LAYERS` block (around line 122):

```python
# Stripe
STRIPE_SECRET_KEY = config("STRIPE_SECRET_KEY", default="")
STRIPE_WEBHOOK_SECRET = config("STRIPE_WEBHOOK_SECRET", default="")
```

**Step 2: Verify settings load**

```bash
cd /Users/k.yook/projects/ai-qr-ordering/backend && poetry run python -c "
import django; import os; os.environ['DJANGO_SETTINGS_MODULE']='config.settings'
django.setup()
from django.conf import settings
print('STRIPE_SECRET_KEY set:', bool(settings.STRIPE_SECRET_KEY))
print('STRIPE_WEBHOOK_SECRET set:', bool(settings.STRIPE_WEBHOOK_SECRET))
"
```

Expected: Both print `True` if env vars are set, `False` if not (both are fine for now).

**Step 3: Commit**

```bash
git add backend/config/settings.py
git commit -m "chore: add Stripe env vars to Django settings"
```

---

### Task 3: Add payment fields to Order model

**Files:**
- Modify: `backend/orders/models.py` (lines 8-15 for Status choices, add fields after line 40)
- Create: migration file (auto-generated)

**Step 1: Update Order model**

In `backend/orders/models.py`, add `PENDING_PAYMENT` to the Status choices (after line 10):

```python
class Status(models.TextChoices):
    PENDING_PAYMENT = "pending_payment", "Pending Payment"
    PENDING = "pending", "Pending"
    CONFIRMED = "confirmed", "Confirmed"
    PREPARING = "preparing", "Preparing"
    READY = "ready", "Ready"
    COMPLETED = "completed", "Completed"
```

Add two new fields after the `total_price` field (after line 40):

```python
    # Payment fields
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("paid", "Paid"),
            ("failed", "Failed"),
            ("refunded", "Refunded"),
        ],
        default="pending",
    )
    stripe_payment_intent_id = models.CharField(
        max_length=255, blank=True, null=True, unique=True,
    )
```

**Step 2: Create and run migration**

```bash
cd /Users/k.yook/projects/ai-qr-ordering/backend && poetry run python manage.py makemigrations orders -n add_payment_fields
```

```bash
cd /Users/k.yook/projects/ai-qr-ordering/backend && POSTGRES_HOST=localhost poetry run python manage.py migrate
```

**Step 3: Run existing tests to verify nothing breaks**

```bash
cd /Users/k.yook/projects/ai-qr-ordering/backend && poetry run pytest orders/tests/test_models.py -v
```

Expected: All pass.

**Step 4: Commit**

```bash
git add backend/orders/models.py backend/orders/migrations/
git commit -m "feat: add payment_status and stripe_payment_intent_id to Order model"
```

---

### Task 4: Update OrderResponseSerializer to include payment fields

**Files:**
- Modify: `backend/orders/serializers.py:44-54`

**Step 1: Add payment fields to serializer**

In `backend/orders/serializers.py`, update `OrderResponseSerializer.Meta.fields` (line 49-53):

```python
    class Meta:
        model = Order
        fields = [
            "id", "status", "table_identifier",
            "customer_name", "customer_phone",
            "subtotal", "tax_rate", "tax_amount", "total_price",
            "payment_status", "stripe_payment_intent_id",
            "created_at", "items",
        ]
```

**Step 2: Commit**

```bash
git add backend/orders/serializers.py
git commit -m "feat: add payment fields to OrderResponseSerializer"
```

---

### Task 5: Create `CreatePaymentView` backend endpoint

**Files:**
- Modify: `backend/orders/views.py` (add new view class)
- Modify: `backend/orders/urls.py` (add route)

**Step 1: Write the new view**

Add this import at the top of `backend/orders/views.py` (after line 1):

```python
import stripe
from django.conf import settings
```

Add the new view class after `ConfirmOrderView` (after line 192). This reuses the same validation/pricing logic from `ConfirmOrderView` but creates a PaymentIntent instead of immediately confirming the order:

```python
class CreatePaymentView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, slug):
        try:
            restaurant = Restaurant.objects.get(slug=slug)
        except Restaurant.DoesNotExist:
            return Response(
                {"detail": "Restaurant not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ConfirmOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if not data["items"]:
            return Response(
                {"detail": "Order must contain at least one item."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate and calculate price server-side (same logic as ConfirmOrderView)
        total_price = Decimal("0.00")
        validated_items = []

        for item_data in data["items"]:
            try:
                menu_item = MenuItem.objects.get(
                    id=item_data["menu_item_id"],
                    category__restaurant=restaurant,
                    is_active=True,
                )
                variant = MenuItemVariant.objects.get(
                    id=item_data["variant_id"],
                    menu_item=menu_item,
                )
            except (MenuItem.DoesNotExist, MenuItemVariant.DoesNotExist):
                return Response(
                    {"detail": "Invalid menu item or variant."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            valid_modifiers = []
            modifier_total = Decimal("0.00")
            for mod_id in item_data.get("modifier_ids", []):
                try:
                    modifier = MenuItemModifier.objects.get(
                        id=mod_id, menu_item=menu_item
                    )
                    valid_modifiers.append(modifier)
                    modifier_total += modifier.price_adjustment
                except MenuItemModifier.DoesNotExist:
                    pass

            quantity = item_data["quantity"]
            line_total = (variant.price + modifier_total) * quantity
            total_price += line_total

            validated_items.append(
                {
                    "menu_item": menu_item,
                    "variant": variant,
                    "quantity": quantity,
                    "special_requests": item_data.get("special_requests", ""),
                    "modifiers": valid_modifiers,
                }
            )

        # Calculate tax
        subtotal = total_price
        tax_rate = restaurant.tax_rate
        tax_amount = (subtotal * tax_rate / Decimal("100")).quantize(Decimal("0.01"))
        grand_total = subtotal + tax_amount

        # Check for customer auth
        customer = None
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if auth_header.startswith("Bearer "):
            try:
                from rest_framework_simplejwt.tokens import UntypedToken
                from customers.models import Customer
                token_str = auth_header.split(" ", 1)[1]
                token = UntypedToken(token_str)
                if token.get("token_type") == "customer_access":
                    customer = Customer.objects.get(id=token["customer_id"])
            except Exception:
                pass

        # Create order with pending_payment status
        order = Order.objects.create(
            restaurant=restaurant,
            table_identifier=data.get("table_identifier") or None,
            customer=customer,
            customer_name=data.get("customer_name", ""),
            customer_phone=data.get("customer_phone", ""),
            status="pending_payment",
            payment_status="pending",
            raw_input=data["raw_input"],
            parsed_json=request.data,
            language_detected=data.get("language", "en"),
            subtotal=subtotal,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            total_price=grand_total,
        )

        for item_data in validated_items:
            order_item = OrderItem.objects.create(
                order=order,
                menu_item=item_data["menu_item"],
                variant=item_data["variant"],
                quantity=item_data["quantity"],
                special_requests=item_data["special_requests"],
            )
            order_item.modifiers.set(item_data["modifiers"])

        # Create Stripe PaymentIntent
        stripe.api_key = settings.STRIPE_SECRET_KEY
        amount_cents = int(grand_total * 100)

        try:
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=restaurant.currency.lower(),
                metadata={
                    "order_id": str(order.id),
                    "restaurant_slug": restaurant.slug,
                },
            )
        except stripe.error.StripeError as e:
            order.delete()
            return Response(
                {"detail": f"Payment setup failed: {str(e)}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        order.stripe_payment_intent_id = intent.id
        order.save(update_fields=["stripe_payment_intent_id"])

        response_data = OrderResponseSerializer(order).data
        response_data["client_secret"] = intent.client_secret

        return Response(response_data, status=status.HTTP_201_CREATED)
```

**Step 2: Add URL route**

In `backend/orders/urls.py`, add the import and route:

Update the import (line 2-5):

```python
from orders.views import (
    PublicMenuView, ParseOrderView, ConfirmOrderView, OrderStatusView,
    KitchenOrderUpdateView, CreatePaymentView,
)
```

Add the new route (after line 10):

```python
    path("order/<slug:slug>/create-payment/", CreatePaymentView.as_view(), name="create-payment"),
```

**Step 3: Commit**

```bash
git add backend/orders/views.py backend/orders/urls.py
git commit -m "feat: add CreatePaymentView endpoint"
```

---

### Task 6: Create Stripe webhook endpoint

**Files:**
- Modify: `backend/orders/views.py` (add new view class)
- Modify: `backend/orders/urls.py` (add route)
- Modify: `backend/config/urls.py` (add webhook route at project level)

**Step 1: Write the webhook view**

Add this to `backend/orders/views.py` after the `CreatePaymentView` class:

```python
class StripeWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET,
            )
        except (ValueError, stripe.error.SignatureVerificationError):
            return Response(
                {"detail": "Invalid webhook signature."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if event["type"] == "payment_intent.succeeded":
            intent = event["data"]["object"]
            try:
                order = Order.objects.get(
                    stripe_payment_intent_id=intent["id"]
                )
            except Order.DoesNotExist:
                return Response(status=status.HTTP_200_OK)

            if order.payment_status != "paid":
                order.status = "confirmed"
                order.payment_status = "paid"
                order.save(update_fields=["status", "payment_status"])
                broadcast_order_to_kitchen(order)

        elif event["type"] == "payment_intent.payment_failed":
            intent = event["data"]["object"]
            try:
                order = Order.objects.get(
                    stripe_payment_intent_id=intent["id"]
                )
                order.payment_status = "failed"
                order.save(update_fields=["payment_status"])
            except Order.DoesNotExist:
                pass

        return Response(status=status.HTTP_200_OK)
```

**Step 2: Add URL route**

In `backend/orders/urls.py`, update import:

```python
from orders.views import (
    PublicMenuView, ParseOrderView, ConfirmOrderView, OrderStatusView,
    KitchenOrderUpdateView, CreatePaymentView, StripeWebhookView,
)
```

Add route:

```python
    path("webhooks/stripe/", StripeWebhookView.as_view(), name="stripe-webhook"),
```

**Step 3: Exempt webhook from CSRF**

The webhook receives raw POST from Stripe, not from the browser. Django REST Framework's `APIView` with no authentication already skips CSRF, so no extra config is needed. But we need to ensure the request body is read as raw bytes for signature verification.

The default DRF parser will parse JSON before the view runs. We need the raw body. Django makes `request.body` available before DRF parsing, so `request.body` in the view works correctly.

**Step 4: Update kitchen status transitions**

In `backend/orders/views.py`, update `VALID_TRANSITIONS` (line 212-216) to include the new status:

```python
VALID_TRANSITIONS = {
    "pending_payment": ["confirmed"],
    "confirmed": ["preparing"],
    "preparing": ["ready"],
    "ready": ["completed"],
}
```

**Step 5: Commit**

```bash
git add backend/orders/views.py backend/orders/urls.py
git commit -m "feat: add Stripe webhook endpoint for payment confirmation"
```

---

### Task 7: Write backend tests for payment flow

**Files:**
- Modify: `backend/orders/tests/test_api_orders.py`

**Step 1: Add test class for CreatePaymentView**

Add the following test class to `backend/orders/tests/test_api_orders.py`:

```python
from unittest.mock import MagicMock


@pytest.mark.django_db
class TestCreatePayment:
    @pytest.fixture
    def menu_setup(self):
        restaurant = RestaurantFactory(slug="payment-test", tax_rate=Decimal("8.875"))
        cat = MenuCategoryFactory(restaurant=restaurant)
        item = MenuItemFactory(category=cat, name="Burger")
        variant = MenuItemVariantFactory(
            menu_item=item, label="Regular", price=Decimal("10.00"), is_default=True
        )
        return {
            "restaurant": restaurant,
            "item": item,
            "variant": variant,
        }

    @patch("orders.views.stripe")
    def test_create_payment_creates_order_and_intent(self, mock_stripe, api_client, menu_setup):
        mock_intent = MagicMock()
        mock_intent.id = "pi_test_123"
        mock_intent.client_secret = "pi_test_123_secret_456"
        mock_stripe.PaymentIntent.create.return_value = mock_intent

        response = api_client.post(
            "/api/order/payment-test/create-payment/",
            {
                "items": [
                    {
                        "menu_item_id": menu_setup["item"].id,
                        "variant_id": menu_setup["variant"].id,
                        "quantity": 2,
                    }
                ],
                "raw_input": "Two burgers",
                "table_identifier": "3",
                "language": "en",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == "pending_payment"
        assert response.data["payment_status"] == "pending"
        assert response.data["client_secret"] == "pi_test_123_secret_456"

        # Verify order in DB
        order = Order.objects.get(id=response.data["id"])
        assert order.stripe_payment_intent_id == "pi_test_123"
        assert order.status == "pending_payment"
        # Subtotal: 10.00 * 2 = 20.00, Tax: 20.00 * 8.875% = 1.78
        assert order.subtotal == Decimal("20.00")
        assert order.tax_amount == Decimal("1.78")
        assert order.total_price == Decimal("21.78")

        # Verify Stripe was called with correct amount in cents
        mock_stripe.PaymentIntent.create.assert_called_once()
        call_kwargs = mock_stripe.PaymentIntent.create.call_args[1]
        assert call_kwargs["amount"] == 2178
        assert call_kwargs["currency"] == "usd"

    @patch("orders.views.stripe")
    def test_create_payment_no_items_rejected(self, mock_stripe, api_client, menu_setup):
        response = api_client.post(
            "/api/order/payment-test/create-payment/",
            {"items": [], "raw_input": "nothing"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        mock_stripe.PaymentIntent.create.assert_not_called()
```

**Step 2: Add test class for StripeWebhookView**

```python
@pytest.mark.django_db
class TestStripeWebhook:
    @patch("orders.views.stripe.Webhook.construct_event")
    @patch("orders.views.broadcast_order_to_kitchen")
    def test_payment_succeeded_confirms_order(self, mock_broadcast, mock_construct, api_client):
        order = OrderFactory(
            status="pending_payment",
            payment_status="pending",
            stripe_payment_intent_id="pi_test_webhook",
        )

        mock_construct.return_value = {
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_test_webhook"}},
        }

        response = api_client.post(
            "/api/webhooks/stripe/",
            data=b"raw_payload",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_sig",
        )
        assert response.status_code == status.HTTP_200_OK

        order.refresh_from_db()
        assert order.status == "confirmed"
        assert order.payment_status == "paid"
        mock_broadcast.assert_called_once_with(order)

    @patch("orders.views.stripe.Webhook.construct_event")
    def test_payment_failed_updates_status(self, mock_construct, api_client):
        order = OrderFactory(
            status="pending_payment",
            payment_status="pending",
            stripe_payment_intent_id="pi_test_fail",
        )

        mock_construct.return_value = {
            "type": "payment_intent.payment_failed",
            "data": {"object": {"id": "pi_test_fail"}},
        }

        response = api_client.post(
            "/api/webhooks/stripe/",
            data=b"raw_payload",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_sig",
        )
        assert response.status_code == status.HTTP_200_OK

        order.refresh_from_db()
        assert order.payment_status == "failed"
        assert order.status == "pending_payment"

    @patch("orders.views.stripe.Webhook.construct_event")
    def test_invalid_signature_rejected(self, mock_construct, api_client):
        mock_construct.side_effect = stripe.error.SignatureVerificationError(
            "bad sig", "sig_header"
        )

        response = api_client.post(
            "/api/webhooks/stripe/",
            data=b"raw_payload",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="bad_sig",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
```

Note: Add `import stripe` to the top imports of the test file.

**Step 3: Run tests**

```bash
cd /Users/k.yook/projects/ai-qr-ordering/backend && poetry run pytest orders/tests/test_api_orders.py -v
```

Expected: All tests pass (both new and existing).

**Step 4: Commit**

```bash
git add backend/orders/tests/test_api_orders.py
git commit -m "test: add tests for create-payment and Stripe webhook endpoints"
```

---

### Task 8: Add Stripe frontend dependencies

**Files:**
- Modify: `frontend/package.json`

**Step 1: Install Stripe packages**

```bash
cd /Users/k.yook/projects/ai-qr-ordering/frontend && yarn add @stripe/stripe-js @stripe/react-stripe-js
```

**Step 2: Verify**

```bash
cd /Users/k.yook/projects/ai-qr-ordering/frontend && yarn build
```

Expected: Build succeeds.

**Step 3: Commit**

```bash
git add frontend/package.json frontend/yarn.lock
git commit -m "chore: add Stripe.js frontend dependencies"
```

---

### Task 9: Add frontend API function and types for `create-payment`

**Files:**
- Modify: `frontend/src/types/index.ts` (add new response type)
- Modify: `frontend/src/lib/api.ts` (add new API function)

**Step 1: Add `CreatePaymentResponse` type**

In `frontend/src/types/index.ts`, add after `OrderResponse` (after line 95):

```typescript
export interface CreatePaymentResponse extends OrderResponse {
  client_secret: string;
}
```

**Step 2: Add `createPayment` API function**

In `frontend/src/lib/api.ts`, add the import of `CreatePaymentResponse` to the existing import block and add the function after `confirmOrder`:

Add `CreatePaymentResponse` to the import from `@/types`:

```typescript
import type {
  PublicMenu,
  ParsedOrderResponse,
  ConfirmOrderItem,
  OrderResponse,
  CreatePaymentResponse,
  CustomerAuthResponse,
  CustomerProfile,
  CustomerOrderHistoryItem,
} from "@/types";
```

Add the function after `confirmOrder`:

```typescript
export async function createPayment(
  slug: string,
  items: ConfirmOrderItem[],
  rawInput: string,
  tableIdentifier: string,
  language: string,
  customerName?: string,
  customerPhone?: string
): Promise<CreatePaymentResponse> {
  return apiFetch<CreatePaymentResponse>(`/api/order/${slug}/create-payment/`, {
    method: "POST",
    body: JSON.stringify({
      items,
      raw_input: rawInput,
      table_identifier: tableIdentifier,
      language,
      customer_name: customerName || "",
      customer_phone: customerPhone || "",
    }),
  });
}
```

**Step 3: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/lib/api.ts
git commit -m "feat: add createPayment API function and types"
```

---

### Task 10: Create `useCreatePayment` hook

**Files:**
- Create: `frontend/src/hooks/use-create-payment.ts`

**Step 1: Write the hook**

```typescript
import { useMutation } from "@tanstack/react-query";
import { createPayment } from "@/lib/api";
import type { ConfirmOrderItem } from "@/types";

interface CreatePaymentParams {
  items: ConfirmOrderItem[];
  rawInput: string;
  tableIdentifier: string;
  language: string;
  customerName?: string;
  customerPhone?: string;
}

export function useCreatePayment(slug: string) {
  return useMutation({
    mutationFn: (params: CreatePaymentParams) =>
      createPayment(
        slug,
        params.items,
        params.rawInput,
        params.tableIdentifier,
        params.language,
        params.customerName,
        params.customerPhone
      ),
  });
}
```

**Step 2: Commit**

```bash
git add frontend/src/hooks/use-create-payment.ts
git commit -m "feat: add useCreatePayment hook"
```

---

### Task 11: Update order store for `payment` step

**Files:**
- Modify: `frontend/src/stores/order-store.ts`

**Step 1: Add `payment` step and `clientSecret` state**

Update the `OrderStep` type (line 3):

```typescript
type OrderStep = "welcome" | "input" | "loading" | "confirmation" | "payment" | "submitted";
```

Add `clientSecret` to the interface (after `error: string | null;`):

```typescript
  clientSecret: string | null;
```

Add action (after `setError`):

```typescript
  setClientSecret: (secret: string | null) => void;
```

Add to `initialState` (after `error: null`):

```typescript
  clientSecret: null,
```

Add the implementation in the `create` body (after `setError`):

```typescript
  setClientSecret: (clientSecret) => set({ clientSecret }),
```

Update `reset` to include `clientSecret: null` in the initial state.

**Step 2: Build to verify**

```bash
cd /Users/k.yook/projects/ai-qr-ordering/frontend && yarn build
```

Expected: Build succeeds.

**Step 3: Commit**

```bash
git add frontend/src/stores/order-store.ts
git commit -m "feat: add payment step and clientSecret to order store"
```

---

### Task 12: Update ConfirmationStep to call `create-payment`

**Files:**
- Modify: `frontend/src/app/order/[slug]/components/ConfirmationStep.tsx`

**Step 1: Replace `useConfirmOrder` with `useCreatePayment`**

Change the import (line 12):

```typescript
import { useCreatePayment } from "@/hooks/use-create-payment";
```

In the component body, replace `useConfirmOrder` (line 40):

```typescript
  const createPaymentMutation = useCreatePayment(slug);
```

Add `setClientSecret` to the destructured store values (around line 22-36):

```typescript
  const {
    parsedItems,
    totalPrice,
    rawInput,
    language,
    tableIdentifier,
    customerName,
    customerPhone,
    setStep,
    setOrderId,
    setError,
    setClientSecret,
    setCustomerName,
    setCustomerPhone,
    removeItem,
    updateItemQuantity,
  } = useOrderStore();
```

**Step 2: Update `handleConfirm` to create payment instead of confirming**

Replace the mutation call inside `handleConfirm`:

```typescript
    createPaymentMutation.mutate(
      { items, rawInput, tableIdentifier, language, customerName, customerPhone },
      {
        onSuccess: (result) => {
          setOrderId(result.id);
          setClientSecret(result.client_secret);
          setStep("payment");
        },
        onError: (err) => {
          setError(err instanceof Error ? err.message : "Failed to create payment");
        },
      }
    );
```

**Step 3: Update the button to use the new mutation**

Update the disabled check and pending state to reference `createPaymentMutation` instead of `confirmOrderMutation`:

```typescript
        <Button
          className="flex-1"
          onClick={handleConfirm}
          disabled={createPaymentMutation.isPending || !customerName.trim()}
        >
          {createPaymentMutation.isPending ? "Setting up payment..." : "Place Order"}
        </Button>
```

**Step 4: Build to verify**

```bash
cd /Users/k.yook/projects/ai-qr-ordering/frontend && yarn build
```

Expected: Build succeeds.

**Step 5: Commit**

```bash
git add frontend/src/app/order/[slug]/components/ConfirmationStep.tsx
git commit -m "feat: update ConfirmationStep to use create-payment flow"
```

---

### Task 13: Create PaymentStep component

**Files:**
- Create: `frontend/src/app/order/[slug]/components/PaymentStep.tsx`

**Step 1: Write the PaymentStep component**

```typescript
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
  const { setStep, setError } = useOrderStore();
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
  slug: string;
}

export function PaymentStep({ slug }: PaymentStepProps) {
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

  return (
    <div className="max-w-lg mx-auto px-4 py-8">
      <h2 className="text-xl font-semibold mb-2">Payment</h2>
      <p className="text-muted-foreground mb-6">
        Total: ${totalPrice}
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
```

**Step 2: Build to verify**

```bash
cd /Users/k.yook/projects/ai-qr-ordering/frontend && yarn build
```

Expected: Build succeeds.

**Step 3: Commit**

```bash
git add frontend/src/app/order/[slug]/components/PaymentStep.tsx
git commit -m "feat: add PaymentStep component with Stripe Payment Element"
```

---

### Task 14: Wire PaymentStep into the order page

**Files:**
- Modify: `frontend/src/app/order/[slug]/page.tsx`

**Step 1: Add PaymentStep import and rendering**

Add import (after the ConfirmationStep import):

```typescript
import { PaymentStep } from "./components/PaymentStep";
```

Add the payment step rendering in the JSX (after the confirmation step line, before the submitted step):

```tsx
      {step === "payment" && <PaymentStep slug={slug} />}
```

**Step 2: Build to verify**

```bash
cd /Users/k.yook/projects/ai-qr-ordering/frontend && yarn build
```

Expected: Build succeeds.

**Step 3: Commit**

```bash
git add frontend/src/app/order/[slug]/page.tsx
git commit -m "feat: wire PaymentStep into order page flow"
```

---

### Task 15: Display total (with tax) on PaymentStep

**Files:**
- Modify: `frontend/src/app/order/[slug]/page.tsx` (pass taxRate to PaymentStep)
- Modify: `frontend/src/app/order/[slug]/components/PaymentStep.tsx` (accept and display taxRate)

**Step 1: Pass `taxRate` to PaymentStep**

In `page.tsx`, update the payment step rendering:

```tsx
      {step === "payment" && <PaymentStep slug={slug} taxRate={menu.tax_rate} />}
```

**Step 2: Update PaymentStep to show total with tax**

In `PaymentStep.tsx`, update the interface:

```typescript
interface PaymentStepProps {
  slug: string;
  taxRate: string;
}
```

Update the component signature:

```typescript
export function PaymentStep({ slug, taxRate }: PaymentStepProps) {
```

Update the total display to include tax:

```tsx
      <p className="text-muted-foreground mb-6">
        Total: $
        {(
          parseFloat(totalPrice) +
          parseFloat(totalPrice) * parseFloat(taxRate) / 100
        ).toFixed(2)}
      </p>
```

**Step 3: Build to verify**

```bash
cd /Users/k.yook/projects/ai-qr-ordering/frontend && yarn build
```

Expected: Build succeeds.

**Step 4: Commit**

```bash
git add frontend/src/app/order/[slug]/page.tsx frontend/src/app/order/[slug]/components/PaymentStep.tsx
git commit -m "feat: display total with tax on PaymentStep"
```

---

### Task 16: Final integration check

**Step 1: Run all backend tests**

```bash
cd /Users/k.yook/projects/ai-qr-ordering/backend && poetry run pytest -v
```

Expected: All tests pass.

**Step 2: Run frontend build**

```bash
cd /Users/k.yook/projects/ai-qr-ordering/frontend && yarn build
```

Expected: Build succeeds with no errors.

**Step 3: Verify env vars are documented**

Ensure the following env vars are needed:
- Backend: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`
- Frontend: `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY`

**Step 4: Commit any remaining changes**

```bash
git add -A && git status
```

If clean, done. If there are changes, commit with appropriate message.
