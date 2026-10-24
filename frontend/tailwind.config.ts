import type { Config } from "tailwindcss";

// Theme colors are stored as OKLCH channels in globals.css so Tailwind's
// opacity modifiers (`bg-accent/10`, `border-danger/30`, …) resolve.
const token = (name: string) => `oklch(var(--c-${name}) / <alpha-value>)`;

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: token("surface"),
          50: token("surface-50"),
          100: token("surface-100"),
          200: token("surface-200"),
          300: token("surface-300"),
        },
        accent: {
          DEFAULT: token("accent"),
          strong: token("accent-strong"),
          light: token("accent-light"),
          dark: token("accent-dark"),
          foreground: token("accent-fg"),
        },
        secondary: {
          DEFAULT: token("secondary"),
          light: token("secondary-light"),
          dark: token("secondary-dark"),
        },
        success: token("success"),
        warning: token("warning"),
        danger: {
          DEFAULT: token("danger"),
          foreground: token("surface-100"),
        },
        primary: token("fg"),
        "t-secondary": token("fg-2"),
        muted: token("fg-3"),
        "t-hover": token("fg-hover"),
      },
      borderColor: {
        themed: {
          DEFAULT: token("border"),
          subtle: token("border-subtle"),
          strong: token("border-strong"),
        },
      },
      backgroundColor: {
        "input-themed": "var(--input-bg)",
      },
      backgroundImage: {
        "arc-gradient": "var(--arc-gradient)",
        "arc-gradient-soft": "var(--arc-gradient-soft)",
        "arc-gradient-line": "var(--arc-gradient-line)",
      },
      fontFamily: {
        sans: ["var(--font-body)"],
        display: ["var(--font-display)"],
        mono: ["var(--font-mono)"],
      },
      borderRadius: {
        DEFAULT: "0.375rem",
        md: "0.5rem",
        lg: "0.6875rem",
        xl: "0.9375rem",
        "2xl": "1.25rem",
        "3xl": "1.75rem",
      },
      boxShadow: {
        resting: "var(--shadow-resting)",
        raised: "var(--shadow-raised)",
        floating: "var(--shadow-floating)",
        lg: "var(--shadow-raised)",
        xl: "var(--shadow-floating)",
        "2xl": "var(--shadow-floating)",
      },
      transitionTimingFunction: {
        DEFAULT: "var(--ease-standard)",
        enter: "var(--ease-enter)",
        exit: "var(--ease-exit)",
      },
      transitionDuration: {
        DEFAULT: "160ms",
      },
      keyframes: {
        "fade-up": {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "none" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "bounce-subtle": {
          "0%, 100%": { translate: "0 0" },
          "50%": { translate: "0 -4px" },
        },
      },
      animation: {
        "fade-up": "fade-up 360ms var(--ease-enter) both",
        "fade-in": "fade-in 240ms var(--ease-standard) both",
        "bounce-subtle": "bounce-subtle 1.6s var(--ease-in-out, ease-in-out) infinite",
      },
    },
  },
  plugins: [],
};
export default config;
