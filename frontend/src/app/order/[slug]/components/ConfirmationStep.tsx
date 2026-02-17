"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { useOrderStore } from "@/stores/order-store";
import { usePreferencesStore } from "@/stores/preferences-store";
import { useConfirmOrder } from "@/hooks/use-confirm-order";
import type { ConfirmOrderItem } from "@/types";

interface ConfirmationStepProps {
  slug: string;
  taxRate: string;
}

export function ConfirmationStep({ slug, taxRate }: ConfirmationStepProps) {
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
  const { allergyNote } = usePreferencesStore();
  const confirmOrderMutation = useConfirmOrder(slug);

  const handleConfirm = () => {
    const items: ConfirmOrderItem[] = parsedItems.map((item) => {
      let specialRequests = item.special_requests;
      if (allergyNote) {
        specialRequests = specialRequests
          ? `${specialRequests} | Allergy: ${allergyNote}`
          : `Allergy: ${allergyNote}`;
      }
      return {
        menu_item_id: item.menu_item_id,
        variant_id: item.variant.id,
        quantity: item.quantity,
        modifier_ids: item.modifiers.map((m) => m.id),
        special_requests: specialRequests,
      };
    });

    confirmOrderMutation.mutate(
      { items, rawInput, tableIdentifier, language },
      {
        onSuccess: (order) => {
          setOrderId(order.id);
          setStep("submitted");
        },
        onError: (err) => {
          setError(err instanceof Error ? err.message : "Failed to place order");
        },
      }
    );
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

      {allergyNote && (
        <div className="mb-4 rounded-md border border-orange-200 bg-orange-50 p-3 text-sm dark:border-orange-800 dark:bg-orange-950">
          <p className="font-medium text-orange-800 dark:text-orange-200">
            Allergy note applied to all items:
          </p>
          <p className="text-orange-700 dark:text-orange-300">{allergyNote}</p>
        </div>
      )}

      <Separator className="my-4" />

      <div className="space-y-1 mb-6">
        <div className="flex justify-between text-sm">
          <span>Subtotal</span>
          <span>${totalPrice}</span>
        </div>
        {parseFloat(taxRate) > 0 && (
          <div className="flex justify-between text-sm text-muted-foreground">
            <span>Tax ({taxRate}%)</span>
            <span>${(parseFloat(totalPrice) * parseFloat(taxRate) / 100).toFixed(2)}</span>
          </div>
        )}
        <div className="flex justify-between text-lg font-bold pt-1">
          <span>Total</span>
          <span>
            ${(parseFloat(totalPrice) + parseFloat(totalPrice) * parseFloat(taxRate) / 100).toFixed(2)}
          </span>
        </div>
      </div>

      <div className="flex gap-2">
        <Button variant="outline" onClick={() => setStep("input")}>
          Add More Items
        </Button>
        <Button
          className="flex-1"
          onClick={handleConfirm}
          disabled={confirmOrderMutation.isPending}
        >
          {confirmOrderMutation.isPending ? "Placing Order..." : "Place Order"}
        </Button>
      </div>
    </div>
  );
}
