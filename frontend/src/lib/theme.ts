// Shared by the client ThemeContext and the server layout's pre-paint script,
// so it must stay a plain module (no "use client").

export const THEMES = ["light", "dark", "neon"] as const;
export type Theme = (typeof THEMES)[number];

export const ACCENTS = ["violet", "blue", "green", "amber", "orange", "coral", "rose", "neutral"] as const;
export type Accent = (typeof ACCENTS)[number];

export const THEME_STORAGE_KEY = "rag-theme";
export const ACCENT_STORAGE_KEY = "rag-accent";
