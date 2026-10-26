"use client";

import { Brain, Regex, ShieldCheck, Zap } from "lucide-react";
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
  // Regex rules and local classifiers answer in well under a millisecond.
  if (value > 0 && value < 1) return `${value.toFixed(value < 0.1 ? 3 : 2)} ms`;
  if (value > 0 && value < 10) return `${value.toFixed(1)} ms`;
  return `${Math.round(value)} ms`;
}

/** Decade ticks for a log axis spanning ``values`` (all > 0). */
export function logTicks(values: number[]): number[] {
  const lo = Math.floor(Math.log10(Math.min(...values)));
  const hi = Math.ceil(Math.log10(Math.max(...values)));
  const ticks = [];
  for (let e = lo; e <= Math.max(hi, lo + 1); e++) ticks.push(Math.pow(10, e));
  return ticks;
}

/**
 * Which scatter points get a direct label: the highest point of any
 * cluster keeps its label, points that would sit on top of it rely on the
 * legend and tooltip. Coordinates are normalized to the plot (0–1).
 */
export function labelledIds(points: { id: number; nx: number; ny: number }[]): Set<number> {
  const keep: { nx: number; ny: number }[] = [];
  const ids = new Set<number>();
  [...points]
    .sort((a, b) => b.ny - a.ny)
    .forEach((p) => {
      if (keep.some((k) => Math.abs(k.nx - p.nx) < 0.14 && Math.abs(k.ny - p.ny) < 0.07)) return;
      keep.push(p);
      ids.add(p.id);
    });
  return ids;
}

export function formatInt(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString();
}

export type ModelKind = "decision" | "llm" | "classifier" | "rules";

const KINDS: Record<ModelKind, { label: string; icon: any; style: string; shape: string; marker: string }> = {
  decision: { label: "Decision", icon: Zap, style: "bg-warning/10 text-warning border-warning/30", shape: "diamond", marker: "◆" },
  llm: { label: "LLM", icon: Brain, style: "bg-accent/10 text-accent border-accent/30", shape: "circle", marker: "●" },
  classifier: { label: "Classifier", icon: ShieldCheck, style: "bg-secondary/10 text-secondary border-secondary/30", shape: "square", marker: "■" },
  rules: { label: "Rules", icon: Regex, style: "bg-surface-200 text-t-hover border-visible", shape: "triangle", marker: "▲" },
};

export const kindInfo = (kind: string) => KINDS[kind as ModelKind] || KINDS.llm;

export function KindBadge({ kind, className }: { kind: ModelKind | string; className?: string }) {
  const info = kindInfo(kind);
  const Icon = info.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wide border",
        info.style,
        className
      )}
    >
      <Icon className="w-3 h-3" />
      {info.label}
    </span>
  );
}

export function KindLegend() {
  return (
    <p className="text-[11px] text-muted mt-1">
      {KINDS.decision.marker} decision model · {KINDS.classifier.marker} classifier · {KINDS.rules.marker} rules ·{" "}
      {KINDS.llm.marker} LLM
    </p>
  );
}

export function ChartTooltip({ active, payload, render }: any) {
  const chrome = useChartChrome();
  if (!active || !payload?.length) return null;
  return (
    <div style={chrome.tooltip} className="px-3 py-2 shadow-lg">
      {render(payload[0].payload, payload)}
    </div>
  );
}

export function shortName(m: any) {
  const name = m.variant ? `${m.model_name} · ${m.variant}` : m.model_name;
  return name.length > 22 ? `${name.slice(0, 21)}…` : name;
}

export function VariantBadge({ variant, className }: { variant?: string | null; className?: string }) {
  if (!variant) return null;
  return (
    <span
      className={cn(
        "inline-flex items-center px-1.5 py-0.5 rounded-md text-[10px] font-medium border border-visible bg-surface-50 text-t-hover",
        className
      )}
      title="Variant — the same model with a different policy or prompt"
    >
      {variant}
    </span>
  );
}

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-surface-200 text-t-secondary",
  running: "bg-accent/15 text-accent",
  stopping: "bg-warning/15 text-warning",
  stopped: "bg-warning/15 text-warning",
  completed: "bg-success/15 text-success",
  failed: "bg-danger/15 text-danger",
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
