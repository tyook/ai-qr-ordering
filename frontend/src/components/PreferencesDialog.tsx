"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { usePreferencesStore } from "@/stores/preferences-store";
import { SPEECH_LANGUAGES } from "@/lib/constants";

interface PreferencesDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function PreferencesDialog({
  open,
  onOpenChange,
}: PreferencesDialogProps) {
  const { preferredLanguage, allergyNote, setPreferredLanguage, setAllergyNote } =
    usePreferencesStore();

  const [lang, setLang] = useState(preferredLanguage);
  const [allergy, setAllergy] = useState(allergyNote);

  // Sync local state when dialog opens
  useEffect(() => {
    if (open) {
      setLang(preferredLanguage);
      setAllergy(allergyNote);
    }
  }, [open, preferredLanguage, allergyNote]);

  const handleSave = () => {
    setPreferredLanguage(lang);
    setAllergyNote(allergy.trim());
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Preferences</DialogTitle>
          <DialogDescription>
            Set your language and allergy information. These will be applied
            automatically when you place orders.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Preferred Language */}
          <div className="space-y-2">
            <Label htmlFor="pref-language">Preferred language</Label>
            <select
              id="pref-language"
              value={lang}
              onChange={(e) => setLang(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {SPEECH_LANGUAGES.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.label}
                </option>
              ))}
            </select>
            <p className="text-xs text-muted-foreground">
              Sets the default voice input language when ordering.
            </p>
          </div>

          {/* Allergy Note */}
          <div className="space-y-2">
            <Label htmlFor="pref-allergy">Allergy note</Label>
            <Textarea
              id="pref-allergy"
              value={allergy}
              onChange={(e) => setAllergy(e.target.value)}
              placeholder="e.g. No peanuts, gluten-free, lactose intolerant"
              rows={3}
            />
            <p className="text-xs text-muted-foreground">
              This note will be automatically added to every item in your order.
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave}>Save</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
