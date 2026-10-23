"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import {
  ACCENTS,
  ACCENT_STORAGE_KEY,
  THEMES,
  THEME_STORAGE_KEY,
  type Accent,
  type Theme,
} from "@/lib/theme";

export type { Accent, Theme };

interface ThemeContextType {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  accent: Accent;
  setAccent: (accent: Accent) => void;
}

const ThemeContext = createContext<ThemeContextType>({
  theme: "neon",
  setTheme: () => {},
  accent: "violet",
  setAccent: () => {},
});

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>("neon");
  const [accent, setAccent] = useState<Accent>("violet");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem(THEME_STORAGE_KEY) as Theme | null;
    if (stored && THEMES.includes(stored)) {
      setTheme(stored);
    }
    const storedAccent = localStorage.getItem(ACCENT_STORAGE_KEY) as Accent | null;
    if (storedAccent && ACCENTS.includes(storedAccent)) {
      setAccent(storedAccent);
    }
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted) return;
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme, mounted]);

  useEffect(() => {
    if (!mounted) return;
    document.documentElement.setAttribute("data-accent", accent);
    localStorage.setItem(ACCENT_STORAGE_KEY, accent);
  }, [accent, mounted]);

  // Prevent flash of wrong theme
  if (!mounted) {
    return <div style={{ visibility: "hidden" }}>{children}</div>;
  }

  return (
    <ThemeContext.Provider value={{ theme, setTheme, accent, setAccent }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
