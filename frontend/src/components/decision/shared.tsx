"use client";

import { Brain, Zap } from "lucide-react";
import { useTheme } from "@/contexts/ThemeContext";
import { cn } from "@/lib/utils";

// Categorical slots, assigned by a model's position in the comparison (never
// by rank) so a model keeps its color across every chart. Validated for CVD
// separation on the app's card surfaces: light steps on light, dark steps on
// the neon/dark themes. Comparisons are capped at 8 models — one slot each.
const SERIES_LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"];
const SERIES_DARK = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"];

// Status colors are reserved for outcome (correct / wrong / no answer) and
// always ship with a text label.
export const STATUS = {
  good: "#0ca30c",
  warning: "#fab219",
  critical: "#d03b3b",
};

export function useSeriesColors() {
  const { theme } = useTheme();
  return theme === "light" ? SERIES_LIGHT : SERIES_DARK;
}

export function useChartChrome() {
  const { theme } = useTheme();
  const light = theme === "light";
  return {
    grid: light ? "#d4d4d8" : "rgba(255,255,255,0.06)",
    axis: light ? "#a1a1aa" : "rgba(255,255,255,0.14)",
    tick: "var(--text-secondary)",
    surface: "var(--surface-100)",
    tooltip: {
      backgroundColor: "var(--surface-50)",
      border: "1px solid var(--input-border)",
      borderRadius: "10px",
      color: "var(--text-primary)",
      fontSize: 12,
    },
  };
}

export function formatCost(value: number | null | undefined, opts: { compact?: boolean } = {}): string {
  if (value === null || value === undefined) return "—";
  if (value === 0) return "$0.00";
  const abs = Math.abs(value);
  if (abs >= 100) return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  if (abs >= 1) return `$${value.toFixed(2)}`;
  if (abs >= 0.01) return `$${value.toFixed(opts.compact ? 3 : 4)}`;
  // Sub-cent values: keep 2 significant digits ($0.0046, $0.000012).
  return `$${value.toPrecision(2)}`;
}

export function formatPct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatMs(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  if (value >= 10_000) return `${(value / 1000).toFixed(0)} s`;
  if (value >= 1000) return `${(value / 1000).toFixed(1)} s`;
  return `${Math.round(value)} ms`;
}

export function formatInt(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString();
}

export function KindBadge({ kind, className }: { kind: "decision" | "llm" | string; className?: string }) {
  const isDecision = kind === "decision";
  const Icon = isDecision ? Zap : Brain;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wide border",
        isDecision
          ? "bg-amber-500/10 text-amber-500 border-amber-500/30"
          : "bg-accent/10 text-accent border-accent/30",
        className
      )}
    >
      <Icon className="w-3 h-3" />
      {isDecision ? "Decision" : "LLM"}
    </span>
  );
}

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-surface-200 text-t-secondary",
  running: "bg-accent/15 text-accent",
  stopping: "bg-amber-500/15 text-amber-500",
  stopped: "bg-amber-500/15 text-amber-500",
  completed: "bg-emerald-500/15 text-emerald-500",
  failed: "bg-red-500/15 text-red-500",
};

export function StatusPill({ status }: { status: string }) {
  return (
    <span className={cn("px-2 py-0.5 rounded-full text-[11px] font-medium capitalize", STATUS_STYLES[status] || STATUS_STYLES.pending)}>
      {status}
    </span>
  );
}

export function SeriesDot({ color }: { color: string }) {
  return <span className="inline-block w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />;
}

export function SectionCard({
  title,
  description,
  actions,
  children,
  className,
}: {
  title?: string;
  description?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("bg-surface-100 rounded-2xl border border-visible p-6", className)}>
      {(title || actions) && (
        <div className="flex items-start justify-between gap-4 mb-4">
          <div>
            {title && <h3 className="text-sm font-semibold text-primary">{title}</h3>}
            {description && <p className="text-xs text-t-secondary mt-0.5">{description}</p>}
          </div>
          {actions}
        </div>
      )}
      {children}
    </div>
  );
}
