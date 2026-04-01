"use client";

import { useTheme } from "@/contexts/ThemeContext";

interface LogoProps {
  size?: number;
  className?: string;
}

const THEME_COLORS: Record<string, { stroke: string; glow?: string }> = {
  neon: { stroke: "#a78bfa", glow: "#8b5cf6" },
  dark: { stroke: "#818cf8", glow: "#6366f1" },
  light: { stroke: "#18181b" },
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
        d="M12 3v16M12 5l9 6M12 12.5l9 6"
        stroke={colors.stroke}
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        filter={colors.glow ? "url(#ansuz-glow)" : undefined}
      />
    </svg>
  );
}
