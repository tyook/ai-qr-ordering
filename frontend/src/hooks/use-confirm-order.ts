import { useMutation } from "@tanstack/react-query";
import { confirmOrder } from "@/lib/api";
import type { ConfirmOrderItem } from "@/types";

interface ConfirmOrderParams {
  items: ConfirmOrderItem[];
  rawInput: string;
  tableIdentifier: string;
  language: string;
}

export function useConfirmOrder(slug: string) {
  return useMutation({
    mutationFn: (params: ConfirmOrderParams) =>
      confirmOrder(
        slug,
        params.items,
        params.rawInput,
        params.tableIdentifier,
        params.language
      ),
  });
}
