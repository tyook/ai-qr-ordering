import { create } from "zustand";
import type { ParsedOrderItem } from "@/types";

type OrderStep = "welcome" | "input" | "loading" | "confirmation" | "payment" | "submitted";

interface OrderState {
  step: OrderStep;
  rawInput: string;
  parsedItems: ParsedOrderItem[];
  parsedAllergies: string[];
  totalPrice: string;
  language: string;
  orderId: string | null;
  tableIdentifier: string;
  customerName: string;
  customerPhone: string;
  error: string | null;
  clientSecret: string | null;
  paymentMode: "stripe" | "pos_collected";

  // Actions
  setStep: (step: OrderStep) => void;
  setRawInput: (input: string) => void;
  setParsedResult: (items: ParsedOrderItem[], allergies: string[], total: string, lang: string) => void;
  removeItem: (index: number) => void;
  updateItemQuantity: (index: number, quantity: number) => void;
  setOrderId: (id: string) => void;
  setTableIdentifier: (table: string) => void;
  setCustomerName: (name: string) => void;
  setCustomerPhone: (phone: string) => void;
  setError: (error: string | null) => void;
  setClientSecret: (secret: string | null) => void;
  setPaymentMode: (mode: "stripe" | "pos_collected") => void;
  reset: () => void;
}

const initialState = {
  step: "welcome" as OrderStep,
  rawInput: "",
  parsedItems: [] as ParsedOrderItem[],
  parsedAllergies: [] as string[],
  totalPrice: "0.00",
  language: "en",
  orderId: null,
  tableIdentifier: "",
  customerName: "",
  customerPhone: "",
  error: null,
  clientSecret: null,
  paymentMode: "stripe" as "stripe" | "pos_collected",
};

export const useOrderStore = create<OrderState>((set) => ({
  ...initialState,

  setStep: (step) => set({ step }),
  setRawInput: (rawInput) => set({ rawInput }),
  setParsedResult: (parsedItems, parsedAllergies, totalPrice, language) =>
    set({ parsedItems, parsedAllergies, totalPrice, language }),
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
  setCustomerName: (customerName) => set({ customerName }),
  setCustomerPhone: (customerPhone) => set({ customerPhone }),
  setError: (error) => set({ error }),
  setClientSecret: (clientSecret) => set({ clientSecret }),
  setPaymentMode: (paymentMode) => set({ paymentMode }),
  reset: () => set(initialState),
}));
