"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { Moon, Sun } from "lucide-react";

type Theme = "light" | "dark";

interface ThemeContextValue {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

const STORAGE_KEY = "health-ai-theme";

function applyTheme(theme: Theme) {
  document.documentElement.classList.remove("theme-light", "theme-dark");
  document.body.classList.remove("theme-light", "theme-dark");
  document.documentElement.classList.add(`theme-${theme}`);
  document.body.classList.add(`theme-${theme}`);

  const themeColor = theme === "dark" ? "#020817" : "#caf0f8";
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", themeColor);
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}

function ThemeToggleButton() {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === "dark";

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      className="fixed bottom-4 right-4 z-[120] inline-flex items-center gap-2 rounded-full border px-3 py-2 text-xs font-semibold shadow-lg backdrop-blur-xl transition-all duration-200 hover:scale-[1.02] active:scale-[0.98]"
      style={{
        background: isDark ? "rgba(7, 20, 40, 0.82)" : "rgba(255, 255, 255, 0.82)",
        borderColor: isDark ? "rgba(144, 224, 239, 0.18)" : "rgba(0, 119, 182, 0.14)",
        color: isDark ? "#caf0f8" : "#03045e",
        boxShadow: isDark
          ? "0 18px 40px rgba(2, 8, 23, 0.38)"
          : "0 18px 40px rgba(0, 119, 182, 0.12)",
      }}
    >
      {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      <span>{isDark ? "Bright Mode" : "Dark Mode"}</span>
    </button>
  );
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY) as Theme | null;
    const systemDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const nextTheme = stored ?? (systemDark ? "dark" : "light");
    setTheme(nextTheme);
    applyTheme(nextTheme);
  }, []);

  useEffect(() => {
    applyTheme(theme);
    window.localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  const value = useMemo<ThemeContextValue>(
    () => ({
      theme,
      setTheme,
      toggleTheme: () => setTheme((current) => (current === "light" ? "dark" : "light")),
    }),
    [theme]
  );

  return (
    <ThemeContext.Provider value={value}>
      {children}
      <ThemeToggleButton />
    </ThemeContext.Provider>
  );
}
