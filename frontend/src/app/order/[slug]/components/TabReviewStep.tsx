"use client";

import { useState } from "react";
import { useOrderStore } from "@/stores/order-store";
import { closeTab, createTabPayment } from "@/lib/api";
import SplitEvenModal from "./SplitEvenModal";
import PayByItemModal from "./PayByItemModal";

interface TabReviewStepProps {
  slug: string;
}

export default function TabReviewStep({ slug }: TabReviewStepProps) {
  const {
    tabId,
    tabOrders,
    tabTotal,
    tabAmountPaid,
    tabAmountRemaining,
    tableIdentifier,
    setStep,
    setTabData,
  } = useOrderStore();

  const [showSplitModal, setShowSplitModal] = useState(false);
  const [showItemModal, setShowItemModal] = useState(false);
  const [closing, setClosing] = useState(false);

  const handleCloseAndPay = async (payType: "full" | "split_even" | "pay_by_item") => {
    if (!tabId) return;

    setClosing(true);
    try {
      const tab = await closeTab(slug, tableIdentifier);
      setTabData(tab);

      if (payType === "split_even") {
        setShowSplitModal(true);
      } else if (payType === "pay_by_item") {
        setShowItemModal(true);
      } else {
        // "full" — create a payment intent for the full remaining amount
        const { client_secret, payment_id } = await createTabPayment(
          slug,
          tab.id,
          "full"
        );
        const store = useOrderStore.getState();
        store.setClientSecret(client_secret);
        store.setTabPaymentId(payment_id);
        store.setTotalPrice(tab.amount_remaining);
        store.setStep("payment");
      }
    } catch {
      setClosing(false);
    }
  };

  const isClosing = parseFloat(tabAmountPaid) > 0;

  return (
    <div className="flex flex-col gap-6 p-4">
      <h2 className="text-xl font-bold text-white">Your Tab</h2>

      {/* Orders list */}
      <div className="flex flex-col gap-4">
        {tabOrders.map((order, idx) => (
          <div key={order.id} className="rounded-lg bg-zinc-800 p-4">
            <div className="mb-2 text-sm font-medium text-zinc-400">
              Order {idx + 1}
            </div>
            {order.items.map((item) => (
              <div key={item.id}>
                <div className="flex justify-between text-sm text-zinc-200">
                  <span>
                    {item.quantity}x {item.name}
                  </span>
                  <span>${item.line_total}</span>
                </div>
                {item.modifiers && item.modifiers.length > 0 && (
                  <div className="ml-4 mt-0.5">
                    {item.modifiers.map((m) => (
                      <p key={m.id} className="text-xs text-zinc-400">
                        + {m.name} (+${m.price_adjustment})
                      </p>
                    ))}
                  </div>
                )}
              </div>
            ))}
            <div className="mt-2 border-t border-zinc-700 pt-2 text-right text-sm text-zinc-300">
              ${order.total_price}
            </div>
          </div>
        ))}
      </div>

      {/* Totals */}
      <div className="rounded-lg bg-zinc-800 p-4">
        <div className="flex justify-between text-zinc-300">
          <span>Total</span>
          <span className="text-lg font-bold text-white">${tabTotal}</span>
        </div>
        {isClosing && (
          <>
            <div className="flex justify-between text-sm text-green-400">
              <span>Paid</span>
              <span>${tabAmountPaid}</span>
            </div>
            <div className="flex justify-between text-sm text-zinc-300">
              <span>Remaining</span>
              <span>${tabAmountRemaining}</span>
            </div>
          </>
        )}
      </div>

      {/* Action buttons */}
      <div className="flex flex-col gap-3">
        <button
          onClick={() => handleCloseAndPay("full")}
          disabled={closing}
          className="w-full rounded-xl bg-white py-3 text-center font-semibold text-black"
        >
          Pay Full Amount (${tabAmountRemaining || tabTotal})
        </button>
        <button
          onClick={() => handleCloseAndPay("split_even")}
          disabled={closing}
          className="w-full rounded-xl bg-zinc-700 py-3 text-center font-semibold text-white"
        >
          Split Evenly
        </button>
        <button
          onClick={() => handleCloseAndPay("pay_by_item")}
          disabled={closing}
          className="w-full rounded-xl bg-zinc-700 py-3 text-center font-semibold text-white"
        >
          Pay By Item
        </button>
        <button
          onClick={() => {
            useOrderStore.setState({ parsedItems: [], parsedAllergies: [], totalPrice: "0.00", rawInput: "" });
            setStep("ordering");
          }}
          className="w-full py-3 text-center text-sm text-zinc-400"
        >
          Order More
        </button>
      </div>

      {showSplitModal && (
        <SplitEvenModal
          slug={slug}
          onClose={() => setShowSplitModal(false)}
        />
      )}
      {showItemModal && (
        <PayByItemModal
          slug={slug}
          onClose={() => setShowItemModal(false)}
        />
      )}
    </div>
  );
}
