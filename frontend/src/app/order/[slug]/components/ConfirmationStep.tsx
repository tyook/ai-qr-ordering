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
