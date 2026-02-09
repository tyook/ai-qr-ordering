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
