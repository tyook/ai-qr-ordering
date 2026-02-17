import { useMutation } from "@tanstack/react-query";
import { parseOrder } from "@/lib/api";
import { useOrderStore } from "@/stores/order-store";

export function useParseOrder(slug: string) {
  const setParsedResult = useOrderStore((s) => s.setParsedResult);
  const setStep = useOrderStore((s) => s.setStep);
  const setError = useOrderStore((s) => s.setError);

  return useMutation({
    mutationFn: (rawInput: string) => parseOrder(slug, rawInput),
    onSuccess: (result) => {
      setParsedResult(result.items, result.total_price, result.language);
      setStep("confirmation");
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : "Failed to parse order");
      setStep("input");
    },
  });
}
