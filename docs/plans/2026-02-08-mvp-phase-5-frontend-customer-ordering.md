# Phase 5: Frontend - Customer Ordering Flow

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the customer-facing ordering pages: a multi-step single-page flow where customers type or speak their order, see the AI-parsed result, edit/confirm, and get a confirmation screen.

**Architecture:** Next.js 14 App Router pages at `/order/[slug]/` and `/order/[slug]/[tableId]/`. State managed with Zustand. Voice input via Web Speech API. All API calls through the shared `apiFetch` client.

**Tech Stack:** Next.js 14, TypeScript, Tailwind CSS, shadcn/ui, Zustand, Web Speech API

**Depends on:** Phase 0 (frontend scaffolding), Phase 3 (backend order APIs)

---

## Task 1: TypeScript Types & API Client Extensions

**Files:**
- Create: `frontend/src/types/index.ts`
- Modify: `frontend/src/lib/api.ts`

**Step 1: Create shared types**

Create `frontend/src/types/index.ts`:

```typescript
// Menu types
export interface MenuItemModifier {
  id: number;
  name: string;
  price_adjustment: string;
}

export interface MenuItemVariant {
  id: number;
  label: string;
  price: string;
  is_default: boolean;
}

export interface MenuItem {
  id: number;
  name: string;
  description: string;
  image_url: string;
  variants: MenuItemVariant[];
  modifiers: MenuItemModifier[];
}

export interface MenuCategory {
  id: number;
  name: string;
  items: MenuItem[];
}

export interface PublicMenu {
  restaurant_name: string;
  categories: MenuCategory[];
}

// Order types
export interface ParsedOrderItem {
  menu_item_id: number;
  name: string;
  variant: {
    id: number;
    label: string;
    price: string;
  };
  quantity: number;
  modifiers: MenuItemModifier[];
  special_requests: string;
  line_total: string;
}

export interface ParsedOrderResponse {
  items: ParsedOrderItem[];
  total_price: string;
  language: string;
}

export interface ConfirmOrderItem {
  menu_item_id: number;
  variant_id: number;
  quantity: number;
  modifier_ids: number[];
  special_requests: string;
}

export interface OrderResponse {
  id: string;
  status: string;
  table_identifier: string | null;
  total_price: string;
  created_at: string;
  items: {
    id: number;
    name: string;
    variant_label: string;
    variant_price: string;
    quantity: number;
    special_requests: string;
  }[];
}
```

**Step 2: Add API helper functions**

Append to `frontend/src/lib/api.ts`:

```typescript
import type {
  PublicMenu,
  ParsedOrderResponse,
  ConfirmOrderItem,
  OrderResponse,
} from "@/types";

export async function fetchMenu(slug: string): Promise<PublicMenu> {
  return apiFetch<PublicMenu>(`/api/order/${slug}/menu/`);
}

export async function parseOrder(
  slug: string,
  rawInput: string
): Promise<ParsedOrderResponse> {
  return apiFetch<ParsedOrderResponse>(`/api/order/${slug}/parse/`, {
    method: "POST",
    body: JSON.stringify({ raw_input: rawInput }),
  });
}

export async function confirmOrder(
  slug: string,
  items: ConfirmOrderItem[],
  rawInput: string,
  tableIdentifier: string,
  language: string
): Promise<OrderResponse> {
  return apiFetch<OrderResponse>(`/api/order/${slug}/confirm/`, {
    method: "POST",
    body: JSON.stringify({
      items,
      raw_input: rawInput,
      table_identifier: tableIdentifier,
      language,
    }),
  });
}

export async function fetchOrderStatus(
  slug: string,
  orderId: string
): Promise<OrderResponse> {
  return apiFetch<OrderResponse>(`/api/order/${slug}/status/${orderId}/`);
}
```

**Step 3: Commit**

```bash
git add frontend/src/
git commit -m "feat: add TypeScript types and API client functions for ordering"
```

---

## Task 2: Order State Store (Zustand)

**Files:**
- Create: `frontend/src/stores/order-store.ts`

**Step 1: Create the store**

Create `frontend/src/stores/order-store.ts`:

```typescript
import { create } from "zustand";
import type { ParsedOrderItem } from "@/types";

type OrderStep = "welcome" | "input" | "loading" | "confirmation" | "submitted";

interface OrderState {
  step: OrderStep;
  rawInput: string;
  parsedItems: ParsedOrderItem[];
  totalPrice: string;
  language: string;
  orderId: string | null;
  tableIdentifier: string;
  error: string | null;

  // Actions
  setStep: (step: OrderStep) => void;
  setRawInput: (input: string) => void;
  setParsedResult: (items: ParsedOrderItem[], total: string, lang: string) => void;
  removeItem: (index: number) => void;
  updateItemQuantity: (index: number, quantity: number) => void;
  setOrderId: (id: string) => void;
  setTableIdentifier: (table: string) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

const initialState = {
  step: "welcome" as OrderStep,
  rawInput: "",
  parsedItems: [],
  totalPrice: "0.00",
  language: "en",
  orderId: null,
  tableIdentifier: "",
  error: null,
};

export const useOrderStore = create<OrderState>((set) => ({
  ...initialState,

  setStep: (step) => set({ step }),
  setRawInput: (rawInput) => set({ rawInput }),
  setParsedResult: (parsedItems, totalPrice, language) =>
    set({ parsedItems, totalPrice, language }),
  removeItem: (index) =>
    set((state) => {
      const newItems = state.parsedItems.filter((_, i) => i !== index);
      const newTotal = newItems
        .reduce((sum, item) => sum + parseFloat(item.line_total), 0)
        .toFixed(2);
      return { parsedItems: newItems, totalPrice: newTotal };
    }),
  updateItemQuantity: (index, quantity) =>
    set((state) => {
      const newItems = [...state.parsedItems];
      const item = { ...newItems[index] };
      const unitPrice = parseFloat(item.line_total) / item.quantity;
      item.quantity = quantity;
      item.line_total = (unitPrice * quantity).toFixed(2);
      newItems[index] = item;
      const newTotal = newItems
        .reduce((sum, i) => sum + parseFloat(i.line_total), 0)
        .toFixed(2);
      return { parsedItems: newItems, totalPrice: newTotal };
    }),
  setOrderId: (orderId) => set({ orderId }),
  setTableIdentifier: (tableIdentifier) => set({ tableIdentifier }),
  setError: (error) => set({ error }),
  reset: () => set(initialState),
}));
```

**Step 2: Commit**

```bash
git add frontend/src/stores/
git commit -m "feat: add Zustand order state store"
```

---

## Task 3: Voice Input Hook

**Files:**
- Create: `frontend/src/hooks/use-speech-recognition.ts`

**Step 1: Create the hook**

Create `frontend/src/hooks/use-speech-recognition.ts`:

```typescript
"use client";

import { useState, useRef, useCallback } from "react";

interface UseSpeechRecognitionReturn {
  isListening: boolean;
  transcript: string;
  startListening: () => void;
  stopListening: () => void;
  isSupported: boolean;
}

export function useSpeechRecognition(): UseSpeechRecognitionReturn {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const recognitionRef = useRef<SpeechRecognition | null>(null);

  const isSupported =
    typeof window !== "undefined" &&
    ("SpeechRecognition" in window || "webkitSpeechRecognition" in window);

  const startListening = useCallback(() => {
    if (!isSupported) return;

    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();

    recognition.continuous = true;
    recognition.interimResults = true;

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let finalTranscript = "";
      for (let i = 0; i < event.results.length; i++) {
        finalTranscript += event.results[i][0].transcript;
      }
      setTranscript(finalTranscript);
    };

    recognition.onerror = () => {
      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognitionRef.current = recognition;
    recognition.start();
    setIsListening(true);
  }, [isSupported]);

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      setIsListening(false);
    }
  }, []);

  return { isListening, transcript, startListening, stopListening, isSupported };
}
```

**Step 2: Add Web Speech API type declarations**

Create `frontend/src/types/speech.d.ts`:

```typescript
interface SpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  onresult: (event: SpeechRecognitionEvent) => void;
  onerror: (event: Event) => void;
  onend: () => void;
}

interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList;
}

interface SpeechRecognitionResultList {
  length: number;
  [index: number]: SpeechRecognitionResult;
}

interface SpeechRecognitionResult {
  [index: number]: SpeechRecognitionAlternative;
  isFinal: boolean;
}

interface SpeechRecognitionAlternative {
  transcript: string;
  confidence: number;
}

interface Window {
  SpeechRecognition: new () => SpeechRecognition;
  webkitSpeechRecognition: new () => SpeechRecognition;
}
```

**Step 3: Commit**

```bash
git add frontend/src/
git commit -m "feat: add Web Speech API hook for voice input"
```

---

## Task 4: Order Page - Step Components

**Files:**
- Create: `frontend/src/app/order/[slug]/components/WelcomeStep.tsx`
- Create: `frontend/src/app/order/[slug]/components/InputStep.tsx`
- Create: `frontend/src/app/order/[slug]/components/LoadingStep.tsx`
- Create: `frontend/src/app/order/[slug]/components/ConfirmationStep.tsx`
- Create: `frontend/src/app/order/[slug]/components/SubmittedStep.tsx`

**Step 1: Create component directory**

```bash
mkdir -p frontend/src/app/order/\[slug\]/components
```

**Step 2: Create WelcomeStep**

Create `frontend/src/app/order/[slug]/components/WelcomeStep.tsx`:

```tsx
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
```

**Step 3: Create InputStep**

Create `frontend/src/app/order/[slug]/components/InputStep.tsx`:

```tsx
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useOrderStore } from "@/stores/order-store";
import { useSpeechRecognition } from "@/hooks/use-speech-recognition";
import { parseOrder } from "@/lib/api";

interface InputStepProps {
  slug: string;
}

export function InputStep({ slug }: InputStepProps) {
  const { setStep, setRawInput, setParsedResult, setError, rawInput } =
    useOrderStore();
  const [input, setInput] = useState(rawInput);
  const { isListening, transcript, startListening, stopListening, isSupported } =
    useSpeechRecognition();

  const currentInput = isListening ? transcript : input;

  const handleSubmit = async () => {
    const text = currentInput.trim();
    if (!text) return;

    setRawInput(text);
    setStep("loading");

    try {
      const result = await parseOrder(slug, text);
      setParsedResult(result.items, result.total_price, result.language);
      setStep("confirmation");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to parse order");
      setStep("input");
    }
  };

  const toggleVoice = () => {
    if (isListening) {
      stopListening();
      setInput(transcript);
    } else {
      startListening();
    }
  };

  return (
    <div className="max-w-lg mx-auto px-4 py-8">
      <h2 className="text-xl font-semibold mb-4">What would you like to order?</h2>
      <p className="text-sm text-muted-foreground mb-4">
        Type your order naturally, e.g. &quot;Two large pepperoni pizzas and a coke&quot;
      </p>

      <Textarea
        value={currentInput}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Type your order here..."
        rows={4}
        className="mb-4"
        disabled={isListening}
      />

      <div className="flex gap-2">
        {isSupported && (
          <Button
            variant={isListening ? "destructive" : "outline"}
            onClick={toggleVoice}
          >
            {isListening ? "Stop Recording" : "Speak Order"}
          </Button>
        )}
        <Button onClick={handleSubmit} disabled={!currentInput.trim()}>
          Submit Order
        </Button>
      </div>

      {useOrderStore.getState().error && (
        <p className="text-destructive mt-4 text-sm">
          {useOrderStore.getState().error}
        </p>
      )}
    </div>
  );
}
```

**Step 4: Create LoadingStep**

Create `frontend/src/app/order/[slug]/components/LoadingStep.tsx`:

```tsx
"use client";

export function LoadingStep() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh]">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mb-4" />
      <p className="text-lg text-muted-foreground">Understanding your order...</p>
    </div>
  );
}
```

**Step 5: Create ConfirmationStep**

Create `frontend/src/app/order/[slug]/components/ConfirmationStep.tsx`:

```tsx
"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { useOrderStore } from "@/stores/order-store";
import { confirmOrder } from "@/lib/api";
import type { ConfirmOrderItem } from "@/types";

interface ConfirmationStepProps {
  slug: string;
}

export function ConfirmationStep({ slug }: ConfirmationStepProps) {
  const {
    parsedItems,
    totalPrice,
    rawInput,
    language,
    tableIdentifier,
    setStep,
    setOrderId,
    setError,
    removeItem,
    updateItemQuantity,
  } = useOrderStore();

  const handleConfirm = async () => {
    const items: ConfirmOrderItem[] = parsedItems.map((item) => ({
      menu_item_id: item.menu_item_id,
      variant_id: item.variant.id,
      quantity: item.quantity,
      modifier_ids: item.modifiers.map((m) => m.id),
      special_requests: item.special_requests,
    }));

    try {
      const order = await confirmOrder(
        slug,
        items,
        rawInput,
        tableIdentifier,
        language
      );
      setOrderId(order.id);
      setStep("submitted");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to place order");
    }
  };

  if (parsedItems.length === 0) {
    return (
      <div className="max-w-lg mx-auto px-4 py-8 text-center">
        <p className="text-muted-foreground mb-4">
          We couldn&apos;t match anything from the menu. Try again?
        </p>
        <Button onClick={() => setStep("input")}>Try Again</Button>
      </div>
    );
  }

  return (
    <div className="max-w-lg mx-auto px-4 py-8">
      <h2 className="text-xl font-semibold mb-4">Confirm Your Order</h2>

      <div className="space-y-3 mb-6">
        {parsedItems.map((item, index) => (
          <Card key={index} className="p-4">
            <div className="flex justify-between items-start">
              <div>
                <p className="font-medium">{item.name}</p>
                <p className="text-sm text-muted-foreground">
                  {item.variant.label} - ${item.variant.price}
                </p>
                {item.modifiers.length > 0 && (
                  <p className="text-sm text-muted-foreground">
                    + {item.modifiers.map((m) => m.name).join(", ")}
                  </p>
                )}
                {item.special_requests && (
                  <p className="text-sm italic">Note: {item.special_requests}</p>
                )}
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    item.quantity > 1
                      ? updateItemQuantity(index, item.quantity - 1)
                      : removeItem(index)
                  }
                >
                  -
                </Button>
                <span className="w-6 text-center">{item.quantity}</span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => updateItemQuantity(index, item.quantity + 1)}
                >
                  +
                </Button>
              </div>
            </div>
            <p className="text-right text-sm font-medium mt-2">
              ${item.line_total}
            </p>
          </Card>
        ))}
      </div>

      <Separator className="my-4" />

      <div className="flex justify-between text-lg font-bold mb-6">
        <span>Total</span>
        <span>${totalPrice}</span>
      </div>

      <div className="flex gap-2">
        <Button variant="outline" onClick={() => setStep("input")}>
          Add More Items
        </Button>
        <Button className="flex-1" onClick={handleConfirm}>
          Place Order
        </Button>
      </div>
    </div>
  );
}
```

**Step 6: Create SubmittedStep**

Create `frontend/src/app/order/[slug]/components/SubmittedStep.tsx`:

```tsx
"use client";

import { useOrderStore } from "@/stores/order-store";

export function SubmittedStep() {
  const { orderId, tableIdentifier } = useOrderStore();

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
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
  );
}
```

**Step 7: Commit**

```bash
git add frontend/src/
git commit -m "feat: add order step components (welcome, input, loading, confirmation, submitted)"
```

---

## Task 5: Order Page (main page component)

**Files:**
- Create: `frontend/src/app/order/[slug]/page.tsx`
- Create: `frontend/src/app/order/[slug]/[tableId]/page.tsx`

**Step 1: Create the main order page**

Create `frontend/src/app/order/[slug]/page.tsx`:

```tsx
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
```

**Step 2: Create the table-aware order page**

Create `frontend/src/app/order/[slug]/[tableId]/page.tsx`:

```tsx
"use client";

import { useEffect } from "react";
import { useParams } from "next/navigation";
import { useOrderStore } from "@/stores/order-store";
import OrderPage from "../page";

export default function TableOrderPage() {
  const params = useParams<{ slug: string; tableId: string }>();
  const setTableIdentifier = useOrderStore((s) => s.setTableIdentifier);

  useEffect(() => {
    setTableIdentifier(params.tableId);
  }, [params.tableId, setTableIdentifier]);

  return <OrderPage />;
}
```

**Step 3: Verify build**

```bash
cd frontend
npm run build
```

Expected: Build succeeds.

**Step 4: Commit**

```bash
git add frontend/src/
git commit -m "feat: add customer ordering pages with multi-step flow"
```
