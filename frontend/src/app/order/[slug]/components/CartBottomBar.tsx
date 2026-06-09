"use client";

import { useState, useRef, useCallback } from "react";
import { ShoppingCart } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useOrderStore } from "@/stores/order-store";

interface CartBottomBarProps {
  taxRate: string;
}

export function CartBottomBar({ taxRate }: CartBottomBarProps) {
  const parsedItems = useOrderStore((s) => s.parsedItems);
  const totalPrice = useOrderStore((s) => s.totalPrice);
  const setStep = useOrderStore((s) => s.setStep);
  const paymentModel = useOrderStore((s) => s.paymentModel);

  const [open, setOpen] = useState(false);
  const hoverTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  const itemCount = parsedItems.reduce((sum, item) => sum + item.quantity, 0);
  const hasItems = itemCount > 0;

  const subtotal = parseFloat(totalPrice);
  const taxAmount = parseFloat(taxRate) > 0 ? (subtotal * parseFloat(taxRate)) / 100 : 0;
  const totalWithTax = (subtotal + taxAmount).toFixed(2);

  const handleMouseEnter = useCallback(() => {
    if (!hasItems) return;
    if (hoverTimeout.current) clearTimeout(hoverTimeout.current);
    setOpen(true);
  }, [hasItems]);

  const handleMouseLeave = useCallback(() => {
    hoverTimeout.current = setTimeout(() => setOpen(false), 200);
  }, []);

  return (
    <div
      className="fixed bottom-0 left-0 right-0 z-50 border-t border-border bg-background/95 backdrop-blur-sm"
      style={{ paddingBottom: "env(safe-area-inset-bottom, 0px)" }}
    >
      <div className="max-w-lg mx-auto px-4 py-3 flex items-center justify-between gap-3">
        <Popover open={open} onOpenChange={setOpen}>
          <PopoverTrigger asChild>
            <button
              className="flex items-center gap-2 min-w-0 cursor-pointer"
              onPointerEnter={handleMouseEnter}
              onPointerLeave={handleMouseLeave}
              onClick={() => hasItems && setOpen(!open)}
              disabled={!hasItems}
            >
              <ShoppingCart className="h-5 w-5 text-muted-foreground shrink-0" />
              <span className="text-sm text-muted-foreground truncate">
                {hasItems
                  ? `${itemCount} item${itemCount !== 1 ? "s" : ""}`
                  : "Cart is empty"}
              </span>
            </button>
          </PopoverTrigger>
          <PopoverContent
            side="top"
            align="start"
            sideOffset={12}
            className="w-80 p-0 rounded-2xl border border-border bg-background shadow-xl"
            onPointerEnter={handleMouseEnter}
            onPointerLeave={handleMouseLeave}
          >
            <div className="px-4 pt-4 pb-2">
              <p className="text-xs uppercase tracking-widest text-muted-foreground">
                Your Cart
              </p>
            </div>
            <div className="max-h-64 overflow-y-auto px-4 divide-y divide-border">
              {parsedItems.map((item, index) => (
                <div key={index} className="flex items-center gap-3 py-3">
                  {item.image_url ? (
                    <img
                      src={item.image_url}
                      alt={item.name}
                      className="w-10 h-10 rounded-lg object-cover shrink-0"
                    />
                  ) : (
                    <div className="w-10 h-10 rounded-lg bg-muted shrink-0" />
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-foreground truncate">
                      {item.name}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Qty {item.quantity}
                    </p>
                  </div>
                  <p className="text-sm font-semibold text-foreground shrink-0">
                    ${item.line_total}
                  </p>
                </div>
              ))}
            </div>
            <div className="border-t border-border px-4 py-3 space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">Subtotal</span>
                <span className="text-xs text-muted-foreground">${totalPrice}</span>
              </div>
              {taxAmount > 0 && (
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">Tax ({taxRate}%)</span>
                  <span className="text-xs text-muted-foreground">${taxAmount.toFixed(2)}</span>
                </div>
              )}
              <div className="flex items-center justify-between pt-1">
                <span className="text-sm font-semibold text-foreground">Total</span>
                <span className="text-sm font-bold gradient-text">${totalWithTax}</span>
              </div>
            </div>
          </PopoverContent>
        </Popover>

        <div className="flex items-center gap-3 shrink-0">
          <span className="text-sm font-semibold text-foreground">
            ${totalWithTax}
          </span>
          <Button
            variant="gradient"
            size="sm"
            className={hasItems ? "glow-primary" : ""}
            disabled={!hasItems}
            onClick={() => setStep("cart")}
          >
            {paymentModel === "tab" ? "Place Order" : "Review Order"}
          </Button>
        </div>
      </div>
    </div>
  );
}
