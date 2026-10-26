"use client";

import { useEffect, useMemo, useState } from "react";
import { Loader2 } from "lucide-react";
import {
  CartesianGrid,
  LabelList,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  ChartTooltip,
  KindLegend,
  SectionCard,
  SeriesDot,
  VariantBadge,
  formatCost,
  formatInt,
  formatMs,
  formatPct,
  kindInfo,
  labelledIds,
  logTicks,
  shortName,
  useChartChrome,
} from "./shared";

/* Panels fed by GET /decision/comparisons/{id}/analysis — the guardrail
 * (binary) view, significance tests, ROC curves, calibration, latency and
 * deployment, difficulty slices and policy sensitivity. */

export function formatCi(ci: number[] | null | undefined, digits = 1): string {
  if (!ci) return "—";
  return `${(ci[0] * 100).toFixed(digits)}–${(ci[1] * 100).toFixed(digits)}%`;
}

const formatP = (p: number | null | undefined) => (p === null || p === undefined ? "—" : p < 0.001 ? "<0.001" : p.toFixed(3));
const num = (v: number | null | undefined, digits = 3) => (v === null || v === undefined ? "—" : v.toFixed(digits));

// One-hue sequential ramp (blue) for magnitude cells — same as the per-label table.
const heat = (v: number | null | undefined) =>
  v === null || v === undefined
    ? "transparent"
    : `rgba(57, 135, 229, ${(0.04 + 0.5 * Math.pow(Math.max(0, Math.min(1, v)), 2)).toFixed(3)})`;

function ModelCell({ m }: { m: any }) {
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
      <SeriesDot color={m.color} />
      <span className="text-primary">{m.model_name}</span>
      <VariantBadge variant={m.variant} />
    </span>
  );
}

const th = "px-2.5 py-2 font-medium text-right whitespace-nowrap";
const td = "px-2.5 py-2 text-right tabular-nums text-t-hover whitespace-nowrap";

/* ═══════════════════════════ Latency vs accuracy ═══════════════════════════ */

export function LatencyTradeoffChart({ models }: { models: any[] }) {
  const chrome = useChartChrome();
  const points = models
    .filter((m) => m.p50_latency_ms !== null && m.p50_latency_ms !== undefined)
    .map((m) => ({ x: m.p50_latency_ms, y: (m.accuracy || 0) * 100, m }));
  const useLog = points.length > 1 && points.every((p) => p.x > 0);
  const ticks = useLog ? logTicks(points.map((p) => p.x)) : undefined;
  const span = ticks ? Math.log10(ticks[ticks.length - 1] / ticks[0]) || 1 : 1;
  const maxX = Math.max(...points.map((p) => p.x), 0) || 1;
  const labelled = labelledIds(
    points.map((p) => ({
      id: p.m.id,
      nx: ticks ? Math.log10(p.x / ticks[0]) / span : p.x / maxX,
      ny: p.y / 100,
    }))
  );
  return (
    <SectionCard
      title="Latency vs accuracy"
      description={`Top-left is best: more accurate and faster. Median latency per request${useLog ? " (log axis)" : ""} — only comparable with the hardware each model ran on.`}
    >
      {points.length === 0 ? (
        <p className="text-sm text-muted py-8 text-center">No latency measured yet.</p>
      ) : (
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 20, right: 56, left: 4, bottom: 8 }}>
              <CartesianGrid stroke={chrome.grid} />
              <XAxis
                type="number"
                dataKey="x"
                name="Median latency"
                scale={useLog ? "log" : "auto"}
                domain={ticks ? [ticks[0], ticks[ticks.length - 1]] : [0, "auto"]}
                ticks={ticks}
                tickFormatter={(v) => formatMs(v)}
                tick={{ fill: chrome.tick, fontSize: 11 }}
                stroke={chrome.axis}
                label={{ value: "Median latency (p50)", position: "insideBottom", offset: -4, fill: chrome.tick, fontSize: 11 }}
              />
              <YAxis
                type="number"
                dataKey="y"
                name="Accuracy"
                domain={[0, 100]}
                tickFormatter={(v) => `${v}%`}
                tick={{ fill: chrome.tick, fontSize: 11 }}
                stroke={chrome.axis}
              />
              <ZAxis range={[90, 90]} />
              <Tooltip
                cursor={{ stroke: chrome.axis }}
                content={
                  <ChartTooltip
                    render={(d: any) => (
                      <>
                        <p className="text-xs font-medium">{d.m.display_name}</p>
                        <p className="text-xs">
                          {formatPct(d.m.accuracy)} accuracy · p50 {formatMs(d.m.p50_latency_ms)} · p95 {formatMs(d.m.p95_latency_ms)}
                        </p>
                        {d.m.deployment?.hardware && <p className="text-[11px] opacity-80">{d.m.deployment.hardware}</p>}
                      </>
                    )}
                  />
                }
              />
              <Legend
                verticalAlign="top"
                height={28}
                wrapperStyle={{ fontSize: 11 }}
                formatter={(value: string) => <span style={{ color: "var(--text-secondary)" }}>{value}</span>}
              />
              {points.map((p) => (
                <Scatter
                  key={p.m.id}
                  name={shortName(p.m)}
                  legendType={kindInfo(p.m.kind).shape as any}
                  data={[p]}
                  fill={p.m.color}
                  stroke="var(--surface-100)"
                  strokeWidth={2}
                  shape={kindInfo(p.m.kind).shape as any}
                >
                  {labelled.has(p.m.id) && (
                    <LabelList dataKey={(d: any) => shortName(d.m)} position="top" style={{ fill: "var(--text-secondary)", fontSize: 10 }} />
                  )}
                </Scatter>
              ))}
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      )}
      <KindLegend />
    </SectionCard>
  );
}

/* ═══════════════════════════ Calibration ═══════════════════════════ */

export function CalibrationChart({ models, analysis }: { models: any[]; analysis: any }) {
  const chrome = useChartChrome();
  const series = models
    .map((m) => {
      const cal = analysis?.models?.[m.id]?.calibration;
      const points = (cal?.bins || [])
        .filter((b: any) => b.count > 0)
        .map((b: any) => ({ x: b.avg_confidence * 100, y: b.accuracy * 100, count: b.count, m }));
      return { m, cal, points, coverage: analysis?.models?.[m.id]?.confidence_coverage };
    })
    .filter((s) => s.cal);

  return (
    <SectionCard
      title="Calibration"
      description="Reliability diagram: when a model says it is X% sure, how often is it right? Points on the dashed diagonal are perfectly calibrated; below it = overconfident."
    >
      {!analysis ? (
        <p className="text-sm text-muted py-8 text-center">Available when the run finishes.</p>
      ) : series.length === 0 ? (
        <p className="text-sm text-muted py-8 text-center">No model reported a confidence.</p>
      ) : (
        <>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 8, right: 16, left: 4, bottom: 12 }}>
                <CartesianGrid stroke={chrome.grid} />
                <XAxis
                  type="number"
                  dataKey="x"
                  domain={[0, 100]}
                  ticks={[0, 25, 50, 75, 100]}
                  tickFormatter={(v) => `${v}%`}
                  tick={{ fill: chrome.tick, fontSize: 11 }}
                  stroke={chrome.axis}
                  label={{ value: "Stated confidence", position: "insideBottom", offset: -4, fill: chrome.tick, fontSize: 11 }}
                />
                <YAxis
                  type="number"
                  dataKey="y"
                  domain={[0, 100]}
                  ticks={[0, 25, 50, 75, 100]}
                  tickFormatter={(v) => `${v}%`}
                  tick={{ fill: chrome.tick, fontSize: 11 }}
                  stroke={chrome.axis}
                />
                <ZAxis range={[40, 40]} />
                <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 100, y: 100 }]} stroke={chrome.axis} strokeDasharray="4 4" ifOverflow="hidden" />
                <Tooltip
                  cursor={false}
                  content={
                    <ChartTooltip
                      render={(d: any) => (
                        <>
                          <p className="text-xs font-medium">{d.m.display_name}</p>
                          <p className="text-xs">
                            Says {d.x.toFixed(0)}% sure → right {d.y.toFixed(0)}% of the time
                          </p>
                          <p className="text-[11px] opacity-80">{formatInt(d.count)} predictions in this bin</p>
                        </>
                      )}
                    />
                  }
                />
                <Legend
                  verticalAlign="top"
                  height={36}
                  wrapperStyle={{ fontSize: 11 }}
                  formatter={(value: string) => <span style={{ color: "var(--text-secondary)" }}>{value}</span>}
                />
                {series.map((s) => (
                  <Scatter
                    key={s.m.id}
                    name={shortName(s.m)}
                    data={s.points}
                    fill={s.m.color}
                    stroke={s.m.color}
                    line={{ strokeWidth: 2 }}
                    lineType="joint"
                    shape="circle"
                  />
                ))}
              </ScatterChart>
            </ResponsiveContainer>
          </div>
          <table className="w-full text-xs mt-3">
            <thead>
              <tr className="text-left text-[10px] uppercase tracking-wider text-muted border-b border-visible">
                <th className="px-2.5 py-2 font-medium">Model</th>
                <th className={th} title="Expected calibration error — 0 is perfect">ECE</th>
                <th className={th} title="Mean squared error of the confidence vs. being right — lower is better">Brier</th>
                <th className={th} title="Average confidence minus accuracy">Over-confidence</th>
                <th className={th} title="Share of predictions that came with a confidence">Coverage</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[color:var(--input-border)]">
              {series.map((s) => (
                <tr key={s.m.id}>
                  <td className="px-2.5 py-2"><ModelCell m={s.m} /></td>
                  <td className={td}>{num(s.cal.ece)}</td>
                  <td className={td}>{num(s.cal.brier)}</td>
                  <td className={td}>{s.cal.overconfidence >= 0 ? "+" : ""}{formatPct(s.cal.overconfidence)}</td>
                  <td className={td}>{formatPct(s.coverage, 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </SectionCard>
  );
}

/* ═══════════════════════════ Guardrail (binary) view ═══════════════════════════ */

export function GuardrailPanel({
  comparisonId,
  models,
  labels,
  analysis,
  onAnalysis,
}: {
  comparisonId: number;
  models: any[];
  labels: any[];
  analysis: any;
  onAnalysis: (a: any) => void;
}) {
  const settings = analysis.settings;
  const [positive, setPositive] = useState<string[]>(settings.positive_labels);
  const [policy, setPolicy] = useState<string>(settings.failure_policy);
  const [prevalence, setPrevalence] = useState<string>(settings.prevalence ? String(settings.prevalence * 100) : "");
  const [fnCost, setFnCost] = useState<string>(String(settings.fn_cost));
  const [fpCost, setFpCost] = useState<string>(String(settings.fp_cost));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setPositive(settings.positive_labels);
    setPolicy(settings.failure_policy);
    setPrevalence(settings.prevalence ? String(settings.prevalence * 100) : "");
    setFnCost(String(settings.fn_cost));
    setFpCost(String(settings.fp_cost));
  }, [settings]);

  const prevalenceValue = prevalence.trim() === "" ? null : Number(prevalence) / 100;
  const dirty =
    positive.join("|") !== settings.positive_labels.join("|") ||
    policy !== settings.failure_policy ||
    prevalenceValue !== (settings.prevalence ?? null) ||
    Number(fnCost) !== settings.fn_cost ||
    Number(fpCost) !== settings.fp_cost;

  const apply = async () => {
    setSaving(true);
    setError(null);
    try {
      onAnalysis(
        await api.updateAnalysisSettings(comparisonId, {
          positive_labels: positive,
          failure_policy: policy,
          prevalence: prevalenceValue !== null && prevalenceValue > 0 && prevalenceValue < 1 ? prevalenceValue : null,
          fn_cost: Math.max(0, Number(fnCost) || 0),
          fp_cost: Math.max(0, Number(fpCost) || 0),
        })
      );
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const toggle = (name: string) =>
    setPositive((prev) => (prev.includes(name) ? prev.filter((l) => l !== name) : labels.map((l) => l.name).filter((n) => n === name || prev.includes(n))));

  const rows = models.map((m) => ({ m, b: analysis.models?.[m.id]?.binary }));
  const sampleShare = rows.find((r) => r.b)?.b?.sample_prevalence;

  return (
    <SectionCard
      title="Guardrail view — block vs allow"
      description="Collapse the labels into one decision: does the text get blocked? Detection rate is the share of attacks caught; over-blocking is the share of legitimate traffic stopped."
    >
      <div className="bg-surface-50 border border-visible rounded-xl p-3 space-y-3 mb-4">
        <div>
          <p className="text-[11px] font-medium text-t-hover mb-1.5">
            Labels that mean <strong className="text-primary">block</strong>
            {settings.auto_detected && settings.enabled && <span className="text-muted font-normal"> (auto-detected — everything except “safe”-like labels)</span>}
          </p>
          <div className="flex flex-wrap gap-1.5">
            {labels.map((l) => {
              const on = positive.includes(l.name);
              return (
                <button
                  key={l.name}
                  onClick={() => toggle(l.name)}
                  aria-pressed={on}
                  className={cn(
                    "px-2 py-1 rounded-md text-[11px] border font-mono transition-colors",
                    on ? "bg-accent/20 border-accent text-accent" : "bg-surface-100 border-visible text-t-hover hover:text-primary"
                  )}
                >
                  {on ? "⛔ " : ""}
                  {l.name}
                </button>
              );
            })}
          </div>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <label className="block">
            <span className="block text-[11px] text-t-hover mb-1">A failed request…</span>
            <select
              value={policy}
              onChange={(e) => setPolicy(e.target.value)}
              className="px-2 py-1.5 bg-surface-100 border border-visible rounded-md text-xs text-primary"
            >
              <option value="open">lets the text through (fail-open)</option>
              <option value="closed">blocks the text (fail-closed)</option>
              <option value="exclude">is left out</option>
            </select>
          </label>
          <label className="block">
            <span className="block text-[11px] text-t-hover mb-1">Attack prevalence in production</span>
            <span className="relative">
              <input
                type="number"
                min={0}
                max={100}
                step="0.1"
                value={prevalence}
                onChange={(e) => setPrevalence(e.target.value)}
                placeholder={sampleShare !== undefined && sampleShare !== null ? `sample: ${(sampleShare * 100).toFixed(1)}` : "sample"}
                className="w-32 pl-2 pr-6 py-1.5 bg-surface-100 border border-visible rounded-md text-xs text-primary"
              />
              <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[11px] text-muted">%</span>
            </span>
          </label>
          <label className="block">
            <span className="block text-[11px] text-t-hover mb-1">Cost of a missed attack</span>
            <input
              type="number"
              min={0}
              step="0.5"
              value={fnCost}
              onChange={(e) => setFnCost(e.target.value)}
              className="w-24 px-2 py-1.5 bg-surface-100 border border-visible rounded-md text-xs text-primary"
            />
          </label>
          <label className="block">
            <span className="block text-[11px] text-t-hover mb-1">Cost of a false block</span>
            <input
              type="number"
              min={0}
              step="0.5"
              value={fpCost}
              onChange={(e) => setFpCost(e.target.value)}
              className="w-24 px-2 py-1.5 bg-surface-100 border border-visible rounded-md text-xs text-primary"
            />
          </label>
          <button
            onClick={apply}
            disabled={!dirty || saving}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-accent text-accent-foreground rounded-md text-xs font-medium hover:bg-accent/90 disabled:opacity-50"
          >
            {saving && <Loader2 className="w-3 h-3 animate-spin" />}
            Apply
          </button>
        </div>
        {error && <p className="text-[11px] text-danger">{error}</p>}
      </div>

      {!settings.enabled ? (
        <p className="text-sm text-muted py-4 text-center">
          Pick at least one label that means “block” (and leave at least one that doesn’t) to see guardrail metrics.
        </p>
      ) : (
        <div className="overflow-x-auto -mx-2">
          <table className="w-full text-xs min-w-[900px]">
            <thead>
              <tr className="text-left text-[10px] uppercase tracking-wider text-muted border-b border-visible">
                <th className="px-2.5 py-2 font-medium">Model</th>
                <th className={th} title="Share of block-worthy texts that were blocked (recall / TPR)">Detection rate</th>
                <th className={th} title="Share of block-worthy texts that got through (FNR)">Missed</th>
                <th className={th} title="Share of legitimate texts that were blocked (FPR)">Over-blocking</th>
                <th className={th} title="Of the texts blocked, the share that deserved it">Precision</th>
                <th className={th}>F1</th>
                <th className={th} title="Mean of detection rate and specificity — robust to class imbalance">Balanced acc.</th>
                <th className={th} title="Matthews correlation coefficient (−1…1)">MCC</th>
                <th className={th} title="Precision if attacks were this share of real traffic">
                  Precision @ {formatPct(rows.find((r) => r.b)?.b?.prevalence_used, 1)}
                </th>
                <th className={th} title="Expected error cost per 1,000 requests at that prevalence, using the costs above">Cost / 1k req.</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[color:var(--input-border)]">
              {rows.map(({ m, b }) => (
                <tr key={m.id} title={b ? `TP ${b.tp} · FN ${b.fn} · FP ${b.fp} · TN ${b.tn}${b.excluded ? ` · ${b.excluded} excluded` : ""}` : ""}>
                  <td className="px-2.5 py-2"><ModelCell m={m} /></td>
                  {b ? (
                    <>
                      <td className={td}>
                        <span className="text-primary font-semibold">{formatPct(b.recall)}</span>
                        <span className="block text-[10px] text-muted">{formatCi(b.recall_ci)}</span>
                      </td>
                      <td className={td}>{formatPct(b.miss_rate)}</td>
                      <td className={td}>
                        <span className="text-primary font-semibold">{formatPct(b.fpr)}</span>
                        <span className="block text-[10px] text-muted">{formatCi(b.fpr_ci)}</span>
                      </td>
                      <td className={td}>{formatPct(b.precision)}</td>
                      <td className={td}>{num(b.f1)}</td>
                      <td className={td}>{formatPct(b.balanced_accuracy)}</td>
                      <td className={td}>{num(b.mcc)}</td>
                      <td className={td}>{formatPct(b.precision_at_prevalence)}</td>
                      <td className={td}>{b.expected_cost_per_1k === null ? "—" : b.expected_cost_per_1k.toFixed(1)}</td>
                    </>
                  ) : (
                    <td colSpan={9} className="px-2.5 py-2 text-muted">No predictions yet.</td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SectionCard>
  );
}

/* ═══════════════════════════ ROC ═══════════════════════════ */

const SOURCE_LABEL: Record<string, string> = {
  probabilities: "probabilities",
  confidence: "stated confidence",
  hard: "hard labels only",
  failed: "failed requests",
};

export function RocPanel({ models, analysis }: { models: any[]; analysis: any }) {
  const chrome = useChartChrome();
  const series = models.map((m) => ({ m, roc: analysis.models?.[m.id]?.roc })).filter((s) => s.roc);
  if (!analysis.settings.enabled || series.length === 0) return null;
  const point = (op: any) =>
    op ? (
      <span title={`threshold ${op.threshold.toFixed(3)}`}>
        {formatPct(op.recall)} <span className="text-muted">@ {formatPct(op.fpr)}</span>
      </span>
    ) : (
      "—"
    );

  return (
    <SectionCard
      title="ROC — block class"
      description="Detection rate vs over-blocking as the decision threshold moves, scored from each model's probabilities (or its stated confidence). Up-left is better; the dashed diagonal is chance."
    >
      <div className="grid grid-cols-1 2xl:grid-cols-2 gap-4">
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 8, right: 16, left: 4, bottom: 12 }}>
              <CartesianGrid stroke={chrome.grid} />
              <XAxis
                type="number"
                dataKey="x"
                domain={[0, 100]}
                ticks={[0, 25, 50, 75, 100]}
                tickFormatter={(v) => `${v}%`}
                tick={{ fill: chrome.tick, fontSize: 11 }}
                stroke={chrome.axis}
                label={{ value: "Over-blocking (FPR)", position: "insideBottom", offset: -4, fill: chrome.tick, fontSize: 11 }}
              />
              <YAxis
                type="number"
                dataKey="y"
                domain={[0, 100]}
                ticks={[0, 25, 50, 75, 100]}
                tickFormatter={(v) => `${v}%`}
                tick={{ fill: chrome.tick, fontSize: 11 }}
                stroke={chrome.axis}
              />
              <ZAxis range={[14, 14]} />
              <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 100, y: 100 }]} stroke={chrome.axis} strokeDasharray="4 4" ifOverflow="hidden" />
              <Tooltip
                cursor={false}
                content={
                  <ChartTooltip
                    render={(d: any) => (
                      <>
                        <p className="text-xs font-medium">{d.m.display_name}</p>
                        <p className="text-xs">
                          Detects {d.y.toFixed(1)}% · over-blocks {d.x.toFixed(1)}%
                        </p>
                        {d.threshold !== null && <p className="text-[11px] opacity-80">threshold ≥ {d.threshold.toFixed(3)}</p>}
                      </>
                    )}
                  />
                }
              />
              <Legend
                verticalAlign="top"
                height={36}
                wrapperStyle={{ fontSize: 11 }}
                formatter={(value: string) => <span style={{ color: "var(--text-secondary)" }}>{value}</span>}
              />
              {series.map(({ m, roc }) => (
                <Scatter
                  key={m.id}
                  name={shortName(m)}
                  data={[...roc.points, { tpr: 1, fpr: 1, threshold: null }].map((p: any) => ({
                    x: p.fpr * 100,
                    y: p.tpr * 100,
                    threshold: p.threshold,
                    m,
                  }))}
                  fill={m.color}
                  stroke={m.color}
                  line={{ strokeWidth: 2 }}
                  lineType="joint"
                  shape="circle"
                />
              ))}
            </ScatterChart>
          </ResponsiveContainer>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-[10px] uppercase tracking-wider text-muted border-b border-visible">
                <th className="px-2.5 py-2 font-medium">Model</th>
                <th className={th} title="Area under the ROC curve — 0.5 is chance, 1 is perfect">ROC-AUC</th>
                <th className={th} title="Average precision (area under the precision–recall curve)">PR-AUC</th>
                <th className={th} title="Best detection rate while over-blocking at most 1%">Det. @ FPR ≤ 1%</th>
                <th className={th} title="Best detection rate while over-blocking at most 5%">Det. @ FPR ≤ 5%</th>
                <th className={th} title="Lowest over-blocking that still detects 95%">FPR @ det. ≥ 95%</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[color:var(--input-border)]">
              {series.map(({ m, roc }) => (
                <tr key={m.id}>
                  <td className="px-2.5 py-2">
                    <ModelCell m={m} />
                    <span className={cn("block text-[10px] ml-4", roc.score_source === "hard" ? "text-warning" : "text-muted")}>
                      scored from {SOURCE_LABEL[roc.score_source] || roc.score_source}
                      {roc.score_source === "hard" && " — a single operating point"}
                    </span>
                  </td>
                  <td className={td}>{num(roc.auc)}</td>
                  <td className={td}>{num(roc.pr_auc)}</td>
                  <td className={td}>{point(roc.recall_at_fpr_1)}</td>
                  <td className={td}>{point(roc.recall_at_fpr_5)}</td>
                  <td className={td}>
                    {roc.fpr_at_recall_95 ? (
                      <span title={`threshold ${roc.fpr_at_recall_95.threshold.toFixed(3)}`}>{formatPct(roc.fpr_at_recall_95.fpr)}</span>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </SectionCard>
  );
}

/* ═══════════════════════════ Significance ═══════════════════════════ */

export function SignificancePanel({ models, analysis }: { models: any[]; analysis: any }) {
  const pairs = useMemo(() => {
    const map = new Map<string, any>();
    (analysis.pairwise || []).forEach((p: any) => map.set(`${p.a}:${p.b}`, p));
    return map;
  }, [analysis.pairwise]);
  if (models.length < 2) return null;

  const cell = (row: any, col: any) => {
    if (row.id === col.id) return <span className="text-muted">—</span>;
    const direct = pairs.get(`${row.id}:${col.id}`);
    const flipped = pairs.get(`${col.id}:${row.id}`);
    const p = direct || flipped;
    if (!p) return <span className="text-muted">·</span>;
    const rowOnly = direct ? p.a_only : p.b_only;
    const colOnly = direct ? p.b_only : p.a_only;
    const glyph = !p.significant ? "≈" : rowOnly > colOnly ? "▲" : "▼";
    return (
      <span
        title={`${row.display_name} right & ${col.display_name} wrong: ${rowOnly}\n${col.display_name} right & ${row.display_name} wrong: ${colOnly}\n${p.n} shared rows · McNemar p = ${formatP(p.p_value)} · Holm-adjusted ${formatP(p.p_adjusted)}`}
      >
        {glyph} <span className="text-[10px] text-muted">{formatP(p.p_adjusted)}</span>
      </span>
    );
  };

  return (
    <SectionCard
      title="Statistical significance"
      description="Paired McNemar test on the rows both models answered. ▲ the row model is significantly more accurate than the column model, ▼ less accurate, ≈ the gap could be noise (α = 0.05, Holm-adjusted p shown)."
    >
      <div className="overflow-x-auto">
        <table className="text-xs border-separate" style={{ borderSpacing: 2 }}>
          <thead>
            <tr>
              <th className="px-2 py-1 text-left text-muted font-medium">row vs column →</th>
              {models.map((m) => (
                <th key={m.id} className="px-2 py-1 text-muted font-medium whitespace-nowrap">
                  <span className="inline-flex items-center gap-1.5 text-[11px] text-t-hover">
                    <SeriesDot color={m.color} />
                    {shortName(m)}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {models.map((row) => (
              <tr key={row.id}>
                <td className="px-2 py-1 whitespace-nowrap">
                  <span className="inline-flex items-center gap-1.5 text-[11px] text-primary">
                    <SeriesDot color={row.color} />
                    {shortName(row)}
                  </span>
                </td>
                {models.map((col) => {
                  const p = pairs.get(`${row.id}:${col.id}`) || pairs.get(`${col.id}:${row.id}`);
                  return (
                    <td
                      key={col.id}
                      className="px-2 py-1.5 text-center tabular-nums text-primary rounded min-w-[84px]"
                      style={{ backgroundColor: row.id !== col.id && p?.significant ? heat(0.8) : "var(--surface-50)" }}
                    >
                      {cell(row, col)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </SectionCard>
  );
}

/* ═══════════════════════════ Latency & deployment ═══════════════════════════ */

export function LatencyPanel({ models, analysis, config }: { models: any[]; analysis: any; config: any }) {
  const hasLlm = models.some((m) => m.kind === "llm");
  return (
    <SectionCard
      title="Latency & deployment"
      description={
        config.latency_mode
          ? `Measured in latency benchmark mode: one request in flight, models one after another${config.warmup ? `, ${config.warmup} discarded warm-up requests each` : ""}.`
          : `Measured with up to ${config.concurrency ?? 8} parallel requests per model and all models running at once — queueing can inflate the tail. Use latency benchmark mode for clean percentiles.`
      }
    >
      <div className="overflow-x-auto -mx-2">
        <table className="w-full text-xs min-w-[900px]">
          <thead>
            <tr className="text-left text-[10px] uppercase tracking-wider text-muted border-b border-visible">
              <th className="px-2.5 py-2 font-medium">Model</th>
              <th className="px-2.5 py-2 font-medium">Runs on</th>
              <th className={th} title="Median with a 95% bootstrap interval">p50</th>
              <th className={th}>p90</th>
              <th className={th}>p95</th>
              <th className={th}>p99</th>
              <th className={th} title="Standard deviation">Std dev</th>
              <th className={th} title="Rows answered per second of wall-clock time">Throughput</th>
              <th className={th} title="Requests that needed more than one attempt (rate limits, 5xx)">Retried</th>
              <th className={th}>Wall time</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[color:var(--input-border)]">
            {models.map((m) => {
              const ci = analysis.models?.[m.id]?.p50_latency_ci;
              const dep = m.deployment || {};
              const runsOn = [dep.hardware, dep.parameters, dep.serving, dep.region].filter(Boolean).join(" · ");
              return (
                <tr key={m.id}>
                  <td className="px-2.5 py-2"><ModelCell m={m} /></td>
                  <td className="px-2.5 py-2 text-t-hover">
                    {runsOn || <span className="text-muted">{m.kind === "rules" ? "in-process" : "not specified"}</span>}
                    {m.infra_cost_per_hour !== null && m.infra_cost_per_hour !== undefined && (
                      <span className="block text-[10px] text-muted">
                        ${Number(m.infra_cost_per_hour).toFixed(2)}/h → {formatCost(m.infra_cost)} for this run
                      </span>
                    )}
                  </td>
                  <td className={td}>
                    <span className="text-primary font-semibold">{formatMs(m.p50_latency_ms)}</span>
                    {ci && <span className="block text-[10px] text-muted">{formatMs(ci[0])}–{formatMs(ci[1])}</span>}
                  </td>
                  <td className={td}>{formatMs(m.p90_latency_ms)}</td>
                  <td className={td}>{formatMs(m.p95_latency_ms)}</td>
                  <td className={td}>{formatMs(m.p99_latency_ms)}</td>
                  <td className={td}>{formatMs(m.latency_std_ms)}</td>
                  <td className={td}>{m.throughput_rps ? `${m.throughput_rps.toFixed(m.throughput_rps < 10 ? 1 : 0)}/s` : "—"}</td>
                  <td className={td}>{m.kind === "llm" ? <span className="text-muted">n/a</span> : formatInt(m.retried)}</td>
                  <td className={td}>{formatMs(m.wall_time_ms)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {hasLlm && (
        <p className="text-[11px] text-muted mt-2">
          Decision-model and classifier latencies time only the attempt that succeeded. LLM latencies include any retries the
          provider SDK makes internally.
        </p>
      )}
    </SectionCard>
  );
}

/* ═══════════════════════════ Slices ═══════════════════════════ */

export function SlicesPanel({ models, analysis }: { models: any[]; analysis: any }) {
  if (!analysis.has_difficulty) return null;
  const groups = Array.from(
    new Set(models.flatMap((m) => Object.keys(analysis.models?.[m.id]?.slices?.difficulty || {})))
  ).sort();
  return (
    <SectionCard
      title="Accuracy by difficulty"
      description="Same rows, split by the dataset's difficulty tag. A model that only wins on easy rows won't hold up on real attacks."
    >
      <div className="overflow-x-auto -mx-2">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-[10px] uppercase tracking-wider text-muted border-b border-visible">
              <th className="px-3 py-2 font-medium">Difficulty</th>
              <th className="px-3 py-2 font-medium text-right">Rows</th>
              {models.map((m) => (
                <th key={m.id} className="px-3 py-2 font-medium text-right whitespace-nowrap">
                  <span className="inline-flex items-center gap-1.5 normal-case tracking-normal text-[11px] text-t-hover">
                    <SeriesDot color={m.color} />
                    {shortName(m)}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[color:var(--input-border)]">
            {groups.map((g) => {
              const n = analysis.models?.[models[0]?.id]?.slices?.difficulty?.[g]?.n ?? 0;
              return (
                <tr key={g}>
                  <td className="px-3 py-1.5"><code className="text-primary">{g}</code></td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-t-secondary">{formatInt(n)}</td>
                  {models.map((m) => {
                    const s = analysis.models?.[m.id]?.slices?.difficulty?.[g];
                    return (
                      <td
                        key={m.id}
                        className="px-3 py-1.5 text-right tabular-nums text-primary"
                        style={{ backgroundColor: heat(s?.accuracy) }}
                        title={s ? `${s.correct} / ${s.n} correct · 95% CI ${formatCi(s.accuracy_ci)}` : ""}
                      >
                        {formatPct(s?.accuracy)}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </SectionCard>
  );
}

/* ═══════════════════════════ Policy sensitivity ═══════════════════════════ */

export function PolicySensitivityPanel({ models, analysis }: { models: any[]; analysis: any }) {
  const groups = analysis.policy_sensitivity || [];
  if (groups.length === 0) return null;
  const byId = Object.fromEntries(models.map((m) => [m.id, m]));
  return (
    <SectionCard
      title="Policy sensitivity"
      description="The same model run with different policies or prompts. A large spread means the wording matters as much as the model — compare models on their best policy, not their default."
    >
      <div className="space-y-4">
        {groups.map((g: any) => (
          <div key={`${g.kind}:${g.model_name}`}>
            <div className="flex items-baseline justify-between gap-2 mb-1.5">
              <p className="text-xs text-primary font-medium">
                {g.model_name} <span className="text-muted font-normal">({g.provider_name})</span>
              </p>
              <p className="text-xs text-t-hover tabular-nums">
                spread <strong className="text-primary">{(g.spread * 100).toFixed(1)} pp</strong>
              </p>
            </div>
            <div className="space-y-1">
              {g.variants.map((v: any) => {
                const m = byId[v.id];
                return (
                  <div key={v.id} className="flex items-center gap-3 text-xs">
                    <span className="w-48 flex items-center gap-1.5 truncate">
                      {m && <SeriesDot color={m.color} />}
                      <span className="truncate text-t-hover">{v.variant || "(no variant name)"}</span>
                    </span>
                    <div className="flex-1 h-1.5 bg-surface-200 rounded-full overflow-hidden">
                      <div className="h-full rounded-full" style={{ width: `${v.accuracy * 100}%`, backgroundColor: m?.color }} />
                    </div>
                    <span className="w-16 text-right tabular-nums text-primary">{formatPct(v.accuracy)}</span>
                    <code className="w-24 text-right text-[10px] text-muted" title="Policy fingerprint">
                      {v.policy_hash}
                    </code>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}
