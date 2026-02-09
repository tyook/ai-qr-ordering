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
