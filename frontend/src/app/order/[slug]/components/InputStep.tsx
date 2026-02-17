"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useOrderStore } from "@/stores/order-store";
import { usePreferencesStore } from "@/stores/preferences-store";
import { useSpeechRecognition } from "@/hooks/use-speech-recognition";
import { useParseOrder } from "@/hooks/use-parse-order";
import { SPEECH_LANGUAGES } from "@/lib/constants";

interface InputStepProps {
  slug: string;
}

export function InputStep({ slug }: InputStepProps) {
  const { setStep, setRawInput, rawInput } = useOrderStore();
  const { preferredLanguage } = usePreferencesStore();
  const [input, setInput] = useState(rawInput);
  const [speechLang, setSpeechLang] = useState(preferredLanguage);
  const { isListening, transcript, startListening, stopListening, isSupported } =
    useSpeechRecognition({ lang: speechLang || undefined });

  const parseOrderMutation = useParseOrder(slug);

  const currentInput = isListening ? transcript : input;

  const handleSubmit = async () => {
    const text = currentInput.trim();
    if (!text) return;

    setRawInput(text);
    setStep("loading");

    parseOrderMutation.mutate(text);
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

      <div className="flex gap-2 flex-wrap">
        {isSupported && (
          <>
            <select
              value={speechLang}
              onChange={(e) => setSpeechLang(e.target.value)}
              disabled={isListening}
              className="rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              {SPEECH_LANGUAGES.map((lang) => (
                <option key={lang.code} value={lang.code}>
                  {lang.label}
                </option>
              ))}
            </select>
            <Button
              variant={isListening ? "destructive" : "outline"}
              onClick={toggleVoice}
            >
              {isListening ? "Stop Recording" : "Speak Order"}
            </Button>
          </>
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
