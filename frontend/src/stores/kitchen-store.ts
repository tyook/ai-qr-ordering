import { create } from "zustand";
import type { OrderResponse } from "@/types";

interface KitchenState {
  orders: OrderResponse[];
  addOrUpdateOrder: (order: OrderResponse) => void;
  getOrdersByStatus: (status: string) => OrderResponse[];
}

export const useKitchenStore = create<KitchenState>((set, get) => ({
  orders: [],

  addOrUpdateOrder: (order) =>
    set((state) => {
      const existing = state.orders.findIndex((o) => o.id === order.id);
      if (existing >= 0) {
        const updated = [...state.orders];
        updated[existing] = order;
        return { orders: updated };
      }
      return { orders: [order, ...state.orders] };
    }),

  getOrdersByStatus: (status) => {
    return get().orders.filter((o) => o.status === status);
  },
}));
