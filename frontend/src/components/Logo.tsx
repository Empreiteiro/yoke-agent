"use client";

import { useTheme } from "@/contexts/ThemeContext";

interface LogoProps {
  size?: number;
  className?: string;
}

// The mark follows the active accent; only the neon theme adds a soft glow.
const THEME_COLORS: Record<string, { stroke: string; glow?: boolean }> = {
  neon: { stroke: "var(--accent)", glow: true },
  dark: { stroke: "var(--accent)" },
  light: { stroke: "var(--accent)" },
};

export default function Logo({ size = 32, className = "" }: LogoProps) {
  const { theme } = useTheme();
  const colors = THEME_COLORS[theme] || THEME_COLORS.neon;

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 32 32"
      width={size}
      height={size}
      className={className}
      fill="none"
    >
      {colors.glow && (
        <defs>
          <filter id="ansuz-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="1.5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
      )}
      <path
        d="M12 5v24M12 5l9 6M12 12.5l9 6"
        stroke={colors.stroke}
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        filter={colors.glow ? "url(#ansuz-glow)" : undefined}
      />
    </svg>
  );
}
