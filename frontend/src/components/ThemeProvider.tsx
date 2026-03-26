"use client";

import { createContext, useContext, useMemo } from "react";
import { usePathname } from "next/navigation";

type ThemeName = "customer" | "admin";

interface ThemeContextValue {
  theme: ThemeName;
}

const ThemeContext = createContext<ThemeContextValue>({ theme: "customer" });

function resolveTheme(pathname: string): ThemeName {
  if (pathname.startsWith("/account/restaurants") || pathname.startsWith("/kitchen")) {
    return "admin";
  }
  return "customer";
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const theme = resolveTheme(pathname);

  const value = useMemo(() => ({ theme }), [theme]);

  return (
    <ThemeContext.Provider value={value}>
      <div data-theme={theme} className="contents">
        {children}
      </div>
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
