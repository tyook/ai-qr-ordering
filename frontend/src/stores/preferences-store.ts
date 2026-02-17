import { create } from "zustand";
import { DEFAULT_LANGUAGE } from "@/lib/constants";

const STORAGE_KEY = "user_preferences";

interface PreferencesState {
  preferredLanguage: string;
  allergyNote: string;

  setPreferredLanguage: (lang: string) => void;
  setAllergyNote: (note: string) => void;
  clearPreferences: () => void;
}

function loadFromStorage(): { preferredLanguage: string; allergyNote: string } {
  if (typeof window === "undefined") {
    return { preferredLanguage: DEFAULT_LANGUAGE, allergyNote: "" };
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      return {
        preferredLanguage: parsed.preferredLanguage ?? DEFAULT_LANGUAGE,
        allergyNote: parsed.allergyNote ?? "",
      };
    }
  } catch {
    // ignore corrupted data
  }
  return { preferredLanguage: DEFAULT_LANGUAGE, allergyNote: "" };
}

function saveToStorage(preferredLanguage: string, allergyNote: string) {
  try {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ preferredLanguage, allergyNote })
    );
  } catch {
    // ignore storage errors
  }
}

export const usePreferencesStore = create<PreferencesState>((set, get) => ({
  ...loadFromStorage(),

  setPreferredLanguage: (preferredLanguage) => {
    set({ preferredLanguage });
    saveToStorage(preferredLanguage, get().allergyNote);
  },

  setAllergyNote: (allergyNote) => {
    set({ allergyNote });
    saveToStorage(get().preferredLanguage, allergyNote);
  },

  clearPreferences: () => {
    set({ preferredLanguage: DEFAULT_LANGUAGE, allergyNote: "" });
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore
    }
  },
}));
