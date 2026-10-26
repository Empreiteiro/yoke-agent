"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  AlertCircle,
  BarChart3,
  ChevronLeft,
  Clock,
  DollarSign,
  Download,
  Loader2,
  Play,
  Plus,
  RotateCcw,
  Search,
  Square,
  Target,
  Timer,
  Trash2,
  Trophy,
  X,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Legend,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { api, downloadFile } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Pager } from "./DecisionDatasets";
import {
  ChartTooltip,
  KindBadge,
  KindLegend,
  STATUS,
  SectionCard,
  SeriesDot,
  StatusPill,
  VariantBadge,
  formatCost,
  formatInt,
  formatMs,
  formatPct,
  kindInfo,
  labelledIds,
  shortName,
  useChartChrome,
  useSeriesColors,
} from "./shared";
import {
  CalibrationChart,
  GuardrailPanel,
  LatencyPanel,
  LatencyTradeoffChart,
  PolicySensitivityPanel,
  RocPanel,
  SignificancePanel,
  SlicesPanel,
  formatCi,
} from "./DecisionAnalysis";

const ACTIVE = ["pending", "running", "stopping"];
const PRED_PAGE = 20;

export default function DecisionResults() {
  const searchParams = useSearchParams();
  const id = searchParams.get("comparison");
  return id ? <ComparisonDetail comparisonId={Number(id)} /> : <ComparisonList />;
}

/* ═══════════════════════════ List ═══════════════════════════ */

function ComparisonList() {
  const router = useRouter();
  const colors = useSeriesColors();
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setRows(await api.listComparisons());
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Keep progress fresh while anything is running.
  useEffect(() => {
    if (!rows.some((r) => ACTIVE.includes(r.status))) return;
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [rows, load]);

  const remove = async (id: number) => {
    if (!confirm("Delete this comparison and all its predictions?")) return;
    try {
      await api.deleteComparison(id);
      setRows((prev) => prev.filter((r) => r.id !== id));
    } catch (e: any) {
      setError(e.message);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-accent/15 flex items-center justify-center">
            <BarChart3 className="w-5 h-5 text-accent" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-primary">Comparison Results</h2>
            <p className="text-sm text-t-secondary">Accuracy, errors and cost for every model you compared.</p>
          </div>
        </div>
        <button
          onClick={() => router.push("/?view=decision-compare")}
          className="flex items-center gap-2 px-4 py-2 bg-accent text-accent-foreground rounded-lg text-sm font-medium hover:bg-accent/90 transition-colors"
        >
          <Plus className="w-4 h-4" />
          New comparison
        </button>
      </div>

      {error && <Banner message={error} onClose={() => setError(null)} />}

      {loading ? (
        <div className="flex items-center justify-center h-48">
          <Loader2 className="w-6 h-6 text-accent animate-spin" />
        </div>
      ) : rows.length === 0 ? (
        <div className="bg-surface-100 rounded-2xl border border-visible p-12 text-center">
          <Trophy className="w-10 h-10 text-muted mx-auto mb-3" />
          <p className="text-sm text-primary font-medium">No comparisons yet</p>
          <p className="text-xs text-t-secondary mt-1">Run decision models and LLMs on the same dataset to see who wins — and at what cost.</p>
          <button
            onClick={() => router.push("/?view=decision-compare")}
            className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-accent text-accent-foreground rounded-lg text-sm font-medium hover:bg-accent/90"
          >
            <Play className="w-4 h-4" /> Start a comparison
          </button>
        </div>
      ) : (
        <div className="bg-surface-100 rounded-2xl border border-visible overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-wider text-muted border-b border-visible">
                <th className="px-4 py-3 font-medium">Comparison</th>
                <th className="px-4 py-3 font-medium">Models</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Best accuracy</th>
                <th className="px-4 py-3 font-medium text-right">Total cost</th>
                <th className="px-4 py-3 font-medium" />
              </tr>
            </thead>
            <tbody className="divide-y divide-[color:var(--input-border)]">
              {rows.map((r) => (
                <tr
                  key={r.id}
                  onClick={() => router.push(`/?view=decision-results&comparison=${r.id}`)}
                  className="cursor-pointer hover:bg-surface-200/30 transition-colors"
                >
                  <td className="px-4 py-3">
                    <p className="text-primary font-medium">{r.name}</p>
                    <p className="text-[11px] text-muted">
                      {r.dataset_name} · {formatInt(r.item_count)} rows · {r.created_at ? new Date(r.created_at + "Z").toLocaleString() : ""}
                    </p>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-col gap-0.5">
                      {r.models.map((m: any, idx: number) => (
                        <span key={m.id} className="inline-flex items-center gap-1.5 text-xs text-t-hover">
                          <SeriesDot color={colors[idx]} />
                          {m.display_name}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <StatusPill status={r.status} />
                    {ACTIVE.includes(r.status) && (
                      <div className="w-24 h-1 bg-surface-200 rounded-full mt-1.5 overflow-hidden">
                        <div className="h-full bg-accent rounded-full" style={{ width: `${(r.progress.ratio || 0) * 100}%` }} />
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {r.best_model ? (
                      <div>
                        <p className="text-primary font-semibold tabular-nums">{formatPct(r.best_model.accuracy)}</p>
                        <p className="text-[11px] text-muted">{r.best_model.display_name}</p>
                      </div>
                    ) : (
                      <span className="text-muted">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right text-primary tabular-nums">{formatCost(r.total_cost)}</td>
                  <td className="px-4 py-3 text-right">
                    {!ACTIVE.includes(r.status) && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          remove(r.id);
                        }}
                        className="p-1.5 rounded-md hover:bg-danger/10"
                        aria-label="Delete comparison"
                      >
                        <Trash2 className="w-4 h-4 text-muted hover:text-danger" />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Banner({ message, onClose }: { message: string; onClose?: () => void }) {
  return (
    <div className="flex items-start gap-2 px-4 py-3 bg-danger/10 border border-danger/20 rounded-xl text-danger text-sm">
      <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
      <span className="flex-1">{message}</span>
      {onClose && (
        <button onClick={onClose}>
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}

/* ═══════════════════════════ Detail ═══════════════════════════ */

function ComparisonDetail({ comparisonId }: { comparisonId: number }) {
  const router = useRouter();
  const colors = useSeriesColors();
  const [comp, setComp] = useState<any>(null);
  const [analysis, setAnalysis] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setComp(await api.getComparison(comparisonId));
    } catch (e: any) {
      setError(e.message);
    }
  }, [comparisonId]);

  useEffect(() => {
    setComp(null);
    setAnalysis(null);
    load();
  }, [load]);

  const running = comp && ACTIVE.includes(comp.status);
  useEffect(() => {
    if (!running) return;
    const t = setInterval(load, 2000);
    return () => clearInterval(t);
  }, [running, load]);

  // Derived statistics are computed server-side from the predictions;
  // fetch them once the run settles (and again if it is resumed).
  const compId: number | undefined = comp?.id;
  const processed: number | undefined = comp?.progress?.processed;
  useEffect(() => {
    if (!compId || running) return;
    api.getComparisonAnalysis(compId).then(setAnalysis).catch((e) => setError(e.message));
  }, [compId, running, processed]);

  const act = async (fn: () => Promise<any>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  // Color follows the model's position in the comparison, never its rank.
  const models = useMemo(
    () => (comp?.models || []).map((m: any, idx: number) => ({ ...m, color: colors[idx % colors.length] })),
    [comp, colors]
  );

  if (!comp) {
    return (
      <div className="space-y-4">
        <BackLink onClick={() => router.push("/?view=decision-results")} />
        {error ? <Banner message={error} /> : <Loader2 className="w-6 h-6 text-accent animate-spin" />}
      </div>
    );
  }

  const finished = models.filter((m: any) => m.accuracy !== null && m.accuracy !== undefined);
  const best = [...finished].sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99))[0];
  const priced = finished.filter((m: any) => m.total_cost !== null && m.total_cost !== undefined);
  const cheapest = [...priced].sort((a, b) => a.total_cost - b.total_cost)[0];
  const fastest = [...finished].filter((m) => m.p50_latency_ms).sort((a, b) => a.p50_latency_ms - b.p50_latency_ms)[0];
  const canResume = !running && models.some((m: any) => m.status !== "completed");

  return (
    <div className="space-y-6">
      <BackLink onClick={() => router.push("/?view=decision-results")} />

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold text-primary">{comp.name}</h2>
            <StatusPill status={comp.status} />
          </div>
          <p className="text-sm text-t-secondary mt-0.5">
            {comp.dataset_name} · {formatInt(comp.item_count)} rows ({comp.sampling}) · {comp.model_count} models
            {comp.config?.latency_mode && (
              <span className="inline-flex items-center gap-1 ml-2 px-1.5 py-0.5 rounded-md border border-visible text-[11px] text-t-hover align-middle">
                <Timer className="w-3 h-3" /> latency benchmark mode
              </span>
            )}
          </p>
          <p className="text-xs text-muted mt-1 max-w-3xl">Task: {comp.task}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {running && (
            <ActionButton icon={Square} label="Stop" disabled={busy || comp.status === "stopping"} onClick={() => act(() => api.stopComparison(comp.id))} />
          )}
          {canResume && (
            <ActionButton icon={RotateCcw} label="Resume / retry" disabled={busy} onClick={() => act(() => api.resumeComparison(comp.id))} />
          )}
          <ActionButton
            icon={Download}
            label="Export CSV"
            onClick={() => downloadFile(`/decision/comparisons/${comp.id}/export`, `comparison_${comp.id}.csv`).catch((e) => setError(e.message))}
          />
          <ActionButton icon={Play} label="New run" onClick={() => router.push(`/?view=decision-compare&dataset=${comp.dataset_id}`)} />
          {!running && (
            <ActionButton
              icon={Trash2}
              label="Delete"
              danger
              disabled={busy}
              onClick={() => {
                if (!confirm("Delete this comparison and all its predictions?")) return;
                act(async () => {
                  await api.deleteComparison(comp.id);
                  router.push("/?view=decision-results");
                });
              }}
            />
          )}
        </div>
      </div>

      {error && <Banner message={error} onClose={() => setError(null)} />}
      {comp.error_message && <Banner message={comp.error_message} />}

      {(running || models.some((m: any) => m.status === "running")) && <ProgressPanel comp={comp} models={models} />}

      {/* KPI tiles */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Kpi
          icon={Trophy}
          label="Most accurate"
          value={best ? formatPct(best.accuracy) : "—"}
          sub={best ? best.display_name : "Waiting for results"}
          color={best?.color}
        />
        <Kpi
          icon={DollarSign}
          label="Cheapest"
          value={cheapest ? formatCost(cheapest.total_cost) : "—"}
          sub={cheapest ? cheapest.display_name : "No priced model yet"}
          color={cheapest?.color}
        />
        <Kpi
          icon={Clock}
          label="Fastest (median)"
          value={fastest ? formatMs(fastest.p50_latency_ms) : "—"}
          sub={fastest ? fastest.display_name : "—"}
          color={fastest?.color}
        />
        <Kpi
          icon={Target}
          label="Comparison total cost"
          value={formatCost(comp.total_cost)}
          sub={`${formatInt(comp.progress.processed)} of ${formatInt(comp.progress.total)} predictions`}
        />
      </div>

      <Leaderboard models={models} analysis={analysis} />

      {finished.length > 0 && (
        <>
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <AccuracyChart models={finished} analysis={analysis} />
            <OutcomeChart models={finished} />
          </div>
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <CostChart models={finished} />
            <TradeoffChart models={finished} />
          </div>
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <LatencyTradeoffChart models={finished} />
            <CalibrationChart models={finished} analysis={analysis} />
          </div>
          {analysis && (
            <>
              <GuardrailPanel
                comparisonId={comp.id}
                models={finished}
                labels={comp.labels}
                analysis={analysis}
                onAnalysis={setAnalysis}
              />
              <RocPanel models={finished} analysis={analysis} />
              <SignificancePanel models={finished} analysis={analysis} />
              <LatencyPanel models={finished} analysis={analysis} config={comp.config || {}} />
              <SlicesPanel models={finished} analysis={analysis} />
              <PolicySensitivityPanel models={finished} analysis={analysis} />
            </>
          )}
          <PerLabelTable models={finished} labels={comp.labels} />
          <ConfusionMatrix models={finished} labels={comp.labels} />
        </>
      )}

      <PredictionsExplorer
        comparisonId={comp.id}
        models={models}
        labels={comp.labels}
        difficulties={Object.keys(firstSlices(analysis))}
        refreshKey={comp.progress.processed}
      />
    </div>
  );
}

function firstSlices(analysis: any): Record<string, any> {
  const first: any = Object.values(analysis?.models || {})[0];
  return first?.slices?.difficulty || {};
}

function BackLink({ onClick }: { onClick: () => void }) {
  return (
    <button onClick={onClick} className="flex items-center gap-1 text-xs text-t-secondary hover:text-primary transition-colors">
      <ChevronLeft className="w-3.5 h-3.5" />
      All comparisons
    </button>
  );
}

function ActionButton({
  icon: Icon,
  label,
  onClick,
  disabled,
  danger,
}: {
  icon: any;
  label: string;
  onClick: () => void;
  disabled?: boolean;
  danger?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "flex items-center gap-1.5 px-3 py-2 text-xs font-medium border border-visible rounded-lg transition-colors disabled:opacity-50",
        danger ? "text-danger hover:bg-danger/10" : "text-t-secondary hover:text-primary hover:bg-surface-200/50"
      )}
    >
      <Icon className="w-3.5 h-3.5" />
      {label}
    </button>
  );
}

function Kpi({ icon: Icon, label, value, sub, color }: { icon: any; label: string; value: string; sub: string; color?: string }) {
  return (
    <div className="bg-surface-100 rounded-2xl border border-visible p-4">
      <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-muted">
        <Icon className="w-3.5 h-3.5" />
        {label}
      </div>
      <p className="text-2xl font-semibold text-primary mt-1.5">{value}</p>
      <p className="text-xs text-t-secondary mt-0.5 flex items-center gap-1.5 truncate">
        {color && <SeriesDot color={color} />}
        <span className="truncate">{sub}</span>
      </p>
    </div>
  );
}

function ProgressPanel({ comp, models }: { comp: any; models: any[] }) {
  return (
    <SectionCard
      title="Progress"
      description={`${formatInt(comp.progress.processed)} of ${formatInt(comp.progress.total)} predictions · refreshing every 2 s`}
    >
      <div className="space-y-2.5">
        {models.map((m) => {
          const ratio = m.total ? m.processed / m.total : 0;
          return (
            <div key={m.id} className="flex items-center gap-3">
              <span className="w-56 flex items-center gap-2 text-xs text-primary truncate">
                <SeriesDot color={m.color} />
                <span className="truncate">{m.display_name}</span>
              </span>
              <div className="flex-1 h-1.5 bg-surface-200 rounded-full overflow-hidden">
                <div className="h-full rounded-full transition-all" style={{ width: `${ratio * 100}%`, backgroundColor: m.color }} />
              </div>
              <span className="w-28 text-right text-[11px] text-t-secondary tabular-nums">
                {formatInt(m.processed)} / {formatInt(m.total)}
              </span>
              <span className="w-20 text-right">
                <StatusPill status={m.status} />
              </span>
            </div>
          );
        })}
      </div>
    </SectionCard>
  );
}

/* ═══════════════════════════ Leaderboard ═══════════════════════════ */

type SortKey = "rank" | "accuracy" | "total_cost" | "cost_per_1k" | "p50_latency_ms" | "macro_f1";

function Leaderboard({ models, analysis }: { models: any[]; analysis: any }) {
  const [sortKey, setSortKey] = useState<SortKey>("rank");
  const [asc, setAsc] = useState(true);

  const sorted = useMemo(() => {
    const val = (m: any) => (m[sortKey] === null || m[sortKey] === undefined ? (asc ? Infinity : -Infinity) : m[sortKey]);
    return [...models].sort((a, b) => (asc ? val(a) - val(b) : val(b) - val(a)));
  }, [models, sortKey, asc]);

  const header = (key: SortKey, label: string, defaultAsc: boolean, className = "") => (
    <th className={cn("px-2.5 py-2.5 font-medium cursor-pointer select-none hover:text-primary", className)}
      onClick={() => {
        if (sortKey === key) setAsc(!asc);
        else {
          setSortKey(key);
          setAsc(defaultAsc);
        }
      }}
    >
      {label}
      {sortKey === key && <span className="ml-0.5">{asc ? "↑" : "↓"}</span>}
    </th>
  );

  return (
    <SectionCard
      title="Leaderboard"
      description="Ranked by accuracy, then total cost. Errors = wrong label + no valid answer. ≈ #1 = not statistically distinguishable from the top model. Click a column to sort."
    >
      <div className="overflow-x-auto -mx-2">
        <table className="w-full text-sm min-w-[900px]">
          <thead>
            <tr className="text-left text-[10px] uppercase tracking-wider text-muted border-b border-visible">
              {header("rank", "#", true, "w-10")}
              <th className="px-2.5 py-2.5 font-medium">Model</th>
              <th className="px-2.5 py-2.5 font-medium text-right">Total</th>
              <th className="px-2.5 py-2.5 font-medium text-right">Correct</th>
              <th className="px-2.5 py-2.5 font-medium text-right">Errors</th>
              {header("accuracy", "Accuracy", false, "text-right")}
              {header("macro_f1", "Macro F1", false, "text-right")}
              {header("total_cost", "Total cost", true, "text-right")}
              {header("cost_per_1k", "Cost / 1k rows", true, "text-right")}
              <th className="px-2.5 py-2.5 font-medium text-right" title="Share of the comparison's total cost · multiple of the cheapest priced model">
                Cost share
              </th>
              {header("p50_latency_ms", "Latency", true, "text-right")}
            </tr>
          </thead>
          <tbody className="divide-y divide-[color:var(--input-border)]">
            {sorted.map((m) => {
              const a = analysis?.models?.[m.id];
              const tie = analysis?.ties_with_best?.[m.id];
              return (
              <tr key={m.id} className="align-top">
                <td className="px-2.5 py-3 text-primary font-semibold tabular-nums">{m.rank ?? "—"}</td>
                <td className="px-2.5 py-3">
                  <div className="flex items-center gap-2 whitespace-nowrap">
                    <SeriesDot color={m.color} />
                    <span className="text-primary font-medium">{m.model_name}</span>
                    <KindBadge kind={m.kind} />
                    <VariantBadge variant={m.variant} />
                    {m.status !== "completed" && <StatusPill status={m.status} />}
                  </div>
                  <p className="text-[11px] text-muted ml-[18px]">
                    {m.provider_name}
                    {m.deployment?.hardware && ` · ${m.deployment.hardware}`}
                    {m.deployment?.parameters && ` · ${m.deployment.parameters}`}
                  </p>
                  {m.error_message && <p className="text-[11px] text-danger ml-[18px] mt-0.5 max-w-md">{m.error_message}</p>}
                </td>
                <td className="px-2.5 py-3 text-right tabular-nums text-t-hover">{formatInt(m.evaluated)}</td>
                <td className="px-2.5 py-3 text-right tabular-nums">
                  <span className="text-primary">{formatInt(m.correct)}</span>
                </td>
                <td className="px-2.5 py-3 text-right tabular-nums">
                  <span className="text-primary">{formatInt(m.errors)}</span>
                  <span className="text-[11px] text-t-secondary ml-1">({formatPct(m.error_rate)})</span>
                  <p className="text-[10px] text-muted">
                    {formatInt(m.incorrect)} wrong · {formatInt(m.failed)} no answer
                  </p>
                </td>
                <td className="px-2.5 py-3 text-right">
                  <span className="text-primary font-semibold tabular-nums">{formatPct(m.accuracy)}</span>
                  {tie && !tie.is_best && tie.tied && (
                    <span
                      className="ml-1 px-1 py-0.5 rounded border border-visible text-[10px] text-t-hover"
                      title={`Not statistically different from the top model (McNemar, Holm-adjusted p = ${tie.p_adjusted?.toFixed(3)})`}
                    >
                      ≈ #1
                    </span>
                  )}
                  <div className="w-20 h-1 bg-surface-200 rounded-full mt-1 ml-auto overflow-hidden">
                    <div className="h-full rounded-full" style={{ width: `${(m.accuracy || 0) * 100}%`, backgroundColor: m.color }} />
                  </div>
                  {a?.accuracy_ci && <p className="text-[10px] text-muted mt-0.5" title="95% Wilson interval">{formatCi(a.accuracy_ci)}</p>}
                </td>
                <td className="px-2.5 py-3 text-right tabular-nums text-t-hover">
                  {m.macro_f1 === null ? "—" : m.macro_f1.toFixed(3)}
                  {a?.macro_f1_ci && (
                    <p className="text-[10px] text-muted" title="95% bootstrap interval">
                      {a.macro_f1_ci[0].toFixed(3)}–{a.macro_f1_ci[1].toFixed(3)}
                    </p>
                  )}
                </td>
                <td className="px-2.5 py-3 text-right tabular-nums text-primary font-medium">
                  {formatCost(m.total_cost)}
                  {m.tokens_estimated && <p className="text-[10px] text-muted font-normal">tokens estimated</p>}
                  {m.infra_cost !== null && m.infra_cost !== undefined && (
                    <p className="text-[10px] text-muted font-normal">incl. {formatCost(m.infra_cost)} hardware</p>
                  )}
                  {!m.pricing_known && <p className="text-[10px] text-warning font-normal">no price set</p>}
                </td>
                <td className="px-2.5 py-3 text-right tabular-nums text-t-hover">{formatCost(m.cost_per_1k)}</td>
                <td className="px-2.5 py-3 text-right tabular-nums text-t-hover">
                  {formatPct(m.cost_share)}
                  {m.cost_vs_cheapest !== null && (
                    <p className="text-[10px] text-muted">
                      {m.cost_vs_cheapest < 1.005 ? "cheapest" : `${m.cost_vs_cheapest.toFixed(m.cost_vs_cheapest < 10 ? 1 : 0)}× min`}
                    </p>
                  )}
                </td>
                <td className="px-2.5 py-3 text-right tabular-nums text-t-hover whitespace-nowrap">
                  {formatMs(m.p50_latency_ms)}
                  <p className="text-[10px] text-muted">p95 {formatMs(m.p95_latency_ms)}</p>
                  <p className="text-[10px] text-muted">p99 {formatMs(m.p99_latency_ms)}</p>
                  {m.retried > 0 && <p className="text-[10px] text-muted">{formatInt(m.retried)} retried</p>}
                </td>
              </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </SectionCard>
  );
}

/* ═══════════════════════════ Charts ═══════════════════════════ */

function AccuracyChart({ models, analysis }: { models: any[]; analysis: any }) {
  const chrome = useChartChrome();
  const data = models.map((m) => ({ name: shortName(m), full: m.display_name, value: (m.accuracy || 0) * 100, m }));
  return (
    <SectionCard title="Accuracy by model" description="Share of rows labeled correctly.">
      <div style={{ height: Math.max(160, data.length * 44 + 40) }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 4, right: 56, left: 8, bottom: 4 }} barCategoryGap={10}>
            <CartesianGrid horizontal={false} stroke={chrome.grid} />
            <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} tick={{ fill: chrome.tick, fontSize: 11 }} stroke={chrome.axis} />
            <YAxis type="category" dataKey="name" width={150} tick={{ fill: chrome.tick, fontSize: 11 }} stroke={chrome.axis} />
            <Tooltip
              cursor={{ fill: "rgba(127,127,127,0.08)" }}
              content={
                <ChartTooltip
                  render={(d: any) => (
                    <>
                      <p className="text-xs font-medium">{d.full}</p>
                      <p className="text-xs">
                        Accuracy <strong>{formatPct(d.m.accuracy)}</strong> · {formatInt(d.m.correct)} / {formatInt(d.m.evaluated)} correct
                      </p>
                      {analysis?.models?.[d.m.id]?.accuracy_ci && (
                        <p className="text-[11px] opacity-80">95% CI {formatCi(analysis.models[d.m.id].accuracy_ci)}</p>
                      )}
                    </>
                  )}
                />
              }
            />
            <Bar dataKey="value" radius={[0, 4, 4, 0]} maxBarSize={22}>
              {data.map((d) => (
                <Cell key={d.m.id} fill={d.m.color} />
              ))}
              <LabelList dataKey="value" position="right" formatter={(v: number) => `${v.toFixed(1)}%`} style={{ fill: "var(--text-primary)", fontSize: 11 }} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </SectionCard>
  );
}

function CostChart({ models }: { models: any[] }) {
  const chrome = useChartChrome();
  const priced = models.filter((m) => m.total_cost !== null && m.total_cost !== undefined);
  const unpriced = models.filter((m) => m.total_cost === null || m.total_cost === undefined);
  const data = priced.map((m) => ({ name: shortName(m), full: m.display_name, value: m.total_cost, m }));
  return (
    <SectionCard title="Total cost by model" description="Measured tokens × price per 1M tokens, for this sample.">
      {data.length === 0 ? (
        <p className="text-sm text-muted py-8 text-center">No model has a price set.</p>
      ) : (
        <div style={{ height: Math.max(160, data.length * 44 + 40) }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} layout="vertical" margin={{ top: 4, right: 72, left: 8, bottom: 4 }} barCategoryGap={10}>
              <CartesianGrid horizontal={false} stroke={chrome.grid} />
              <XAxis type="number" tickFormatter={(v) => formatCost(v, { compact: true })} tick={{ fill: chrome.tick, fontSize: 11 }} stroke={chrome.axis} />
              <YAxis type="category" dataKey="name" width={150} tick={{ fill: chrome.tick, fontSize: 11 }} stroke={chrome.axis} />
              <Tooltip
                cursor={{ fill: "rgba(127,127,127,0.08)" }}
                content={
                  <ChartTooltip
                    render={(d: any) => (
                      <>
                        <p className="text-xs font-medium">{d.full}</p>
                        <p className="text-xs">
                          Total <strong>{formatCost(d.m.total_cost)}</strong> · {formatCost(d.m.cost_per_1k)} per 1k rows
                        </p>
                        <p className="text-[11px] opacity-80">
                          {formatInt(d.m.input_tokens)} in / {formatInt(d.m.output_tokens)} out tokens
                        </p>
                      </>
                    )}
                  />
                }
              />
              <Bar dataKey="value" radius={[0, 4, 4, 0]} maxBarSize={22}>
                {data.map((d) => (
                  <Cell key={d.m.id} fill={d.m.color} />
                ))}
                <LabelList dataKey="value" position="right" formatter={(v: number) => formatCost(v)} style={{ fill: "var(--text-primary)", fontSize: 11 }} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      {unpriced.length > 0 && (
        <p className="text-[11px] text-warning mt-2">
          Not shown (no price): {unpriced.map((m) => m.model_name).join(", ")}
        </p>
      )}
    </SectionCard>
  );
}

function OutcomeChart({ models }: { models: any[] }) {
  const chrome = useChartChrome();
  const data = models.map((m) => {
    const n = m.evaluated || 1;
    return {
      name: shortName(m),
      full: m.display_name,
      correct: (m.correct / n) * 100,
      incorrect: (m.incorrect / n) * 100,
      failed: (m.failed / n) * 100,
      m,
    };
  });
  const inside = (fill: string) => (props: any) => {
    const { x, y, width, height, value } = props;
    if (!value || width < 34) return null;
    return (
      <text x={x + width / 2} y={y + height / 2} dy={4} textAnchor="middle" fontSize={10} fill={fill}>
        {`${value.toFixed(0)}%`}
      </text>
    );
  };
  return (
    <SectionCard title="Outcome breakdown" description="Correct, wrong label and no valid answer, as % of rows.">
      <div style={{ height: Math.max(180, data.length * 44 + 70) }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, left: 8, bottom: 4 }} barCategoryGap={10}>
            <CartesianGrid horizontal={false} stroke={chrome.grid} />
            <XAxis
              type="number"
              domain={[0, 100]}
              ticks={[0, 25, 50, 75, 100]}
              allowDataOverflow
              tickFormatter={(v) => `${Math.round(v)}%`}
              tick={{ fill: chrome.tick, fontSize: 11 }}
              stroke={chrome.axis}
            />
            <YAxis type="category" dataKey="name" width={150} tick={{ fill: chrome.tick, fontSize: 11 }} stroke={chrome.axis} />
            <Tooltip
              cursor={{ fill: "rgba(127,127,127,0.08)" }}
              content={
                <ChartTooltip
                  render={(d: any) => (
                    <>
                      <p className="text-xs font-medium">{d.full}</p>
                      <p className="text-xs">Correct {formatInt(d.m.correct)} ({formatPct(d.m.correct / (d.m.evaluated || 1))})</p>
                      <p className="text-xs">Wrong label {formatInt(d.m.incorrect)} ({formatPct(d.m.incorrect_rate)})</p>
                      <p className="text-xs">No answer {formatInt(d.m.failed)} ({formatPct(d.m.failure_rate)})</p>
                    </>
                  )}
                />
              }
            />
            <Legend
              wrapperStyle={{ fontSize: 11 }}
              formatter={(value: string) => <span style={{ color: "var(--text-secondary)" }}>{value}</span>}
            />
            <Bar dataKey="correct" name="Correct" stackId="o" fill={STATUS.good} stroke="var(--surface-100)" strokeWidth={2} maxBarSize={22}>
              <LabelList dataKey="correct" content={inside("#ffffff")} />
            </Bar>
            <Bar dataKey="incorrect" name="Wrong label" stackId="o" fill={STATUS.critical} stroke="var(--surface-100)" strokeWidth={2} maxBarSize={22}>
              <LabelList dataKey="incorrect" content={inside("#ffffff")} />
            </Bar>
            <Bar dataKey="failed" name="No answer" stackId="o" fill={STATUS.warning} stroke="var(--surface-100)" strokeWidth={2} radius={[0, 4, 4, 0]} maxBarSize={22}>
              <LabelList dataKey="failed" content={inside("#0b0b0b")} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </SectionCard>
  );
}

function TradeoffChart({ models }: { models: any[] }) {
  const chrome = useChartChrome();
  const points = models
    .filter((m) => m.cost_per_1k !== null && m.cost_per_1k !== undefined)
    .map((m) => ({ x: m.cost_per_1k, y: (m.accuracy || 0) * 100, m }));
  const useLog = points.length > 1 && points.every((p) => p.x > 0);
  const maxX = Math.max(...points.map((p) => p.x), 0) || 1;
  const labelled = labelledIds(points.map((p) => ({ id: p.m.id, nx: p.x / maxX, ny: p.y / 100 })));
  return (
    <SectionCard
      title="Cost vs accuracy"
      description={`Top-left is best: higher accuracy for less money.${useLog ? " Cost axis is logarithmic." : ""}`}
    >
      {points.length === 0 ? (
        <p className="text-sm text-muted py-8 text-center">Set prices to plot the trade-off.</p>
      ) : (
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 20, right: 56, left: 4, bottom: 8 }}>
              <CartesianGrid stroke={chrome.grid} />
              <XAxis
                type="number"
                dataKey="x"
                name="Cost per 1k rows"
                scale={useLog ? "log" : "auto"}
                domain={useLog ? ["auto", "auto"] : [0, "auto"]}
                tickFormatter={(v) => formatCost(v, { compact: true })}
                tick={{ fill: chrome.tick, fontSize: 11 }}
                stroke={chrome.axis}
                label={{ value: "Cost per 1k rows", position: "insideBottom", offset: -4, fill: chrome.tick, fontSize: 11 }}
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
                          {formatPct(d.m.accuracy)} accuracy · {formatCost(d.m.cost_per_1k)} per 1k rows
                        </p>
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

/* ═══════════════════════════ Per-label & confusion ═══════════════════════════ */

// One-hue sequential ramp (blue) for magnitude cells; text keeps the ink color.
const heat = (v: number | null | undefined) =>
  v === null || v === undefined
    ? "transparent"
    : `rgba(57, 135, 229, ${(0.04 + 0.5 * Math.pow(Math.max(0, Math.min(1, v)), 2)).toFixed(3)})`;

function PerLabelTable({ models, labels }: { models: any[]; labels: any[] }) {
  return (
    <SectionCard
      title="Accuracy per label"
      description="Recall per label: of the rows whose expected label is X, the share each model got right. Hover a cell for precision and F1."
    >
      <div className="overflow-x-auto -mx-2">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-[10px] uppercase tracking-wider text-muted border-b border-visible">
              <th className="px-3 py-2 font-medium">Label</th>
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
            {labels.map((l: any) => {
              const support = models[0]?.per_label?.[l.name]?.support ?? 0;
              return (
                <tr key={l.name}>
                  <td className="px-3 py-1.5">
                    <code className="text-primary">{l.name}</code>
                  </td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-t-secondary">{formatInt(support)}</td>
                  {models.map((m) => {
                    const s = m.per_label?.[l.name];
                    return (
                      <td
                        key={m.id}
                        className="px-3 py-1.5 text-right tabular-nums text-primary"
                        style={{ backgroundColor: heat(s?.recall) }}
                        title={s ? `Precision ${formatPct(s.precision)} · Recall ${formatPct(s.recall)} · F1 ${s.f1 === null ? "—" : s.f1.toFixed(3)} · predicted ${s.predicted}×` : ""}
                      >
                        {formatPct(s?.recall)}
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

function ConfusionMatrix({ models, labels }: { models: any[]; labels: any[] }) {
  const [modelId, setModelId] = useState<number>(models[0]?.id);
  const model = models.find((m) => m.id === modelId) || models[0];
  const names = labels.map((l: any) => l.name);
  const confusion = model?.confusion || {};
  const hasNoAnswer = Object.values(confusion).some((row: any) => row["(no answer)"]);
  const columns = hasNoAnswer ? [...names, "(no answer)"] : names;

  return (
    <SectionCard
      title="Confusion matrix"
      description="Rows: expected label · columns: predicted label. Shading is the share of each row."
      actions={
        <select
          value={model?.id}
          onChange={(e) => setModelId(Number(e.target.value))}
          className="bg-surface-50 border border-visible rounded-lg px-2 py-1.5 text-xs text-primary focus:outline-none focus:border-accent/50"
        >
          {models.map((m) => (
            <option key={m.id} value={m.id}>
              {m.display_name}
            </option>
          ))}
        </select>
      }
    >
      <div className="overflow-x-auto">
        <table className="text-[11px] border-separate" style={{ borderSpacing: 2 }}>
          <thead>
            <tr>
              <th className="px-2 py-1 text-left text-muted font-medium">expected ↓ / predicted →</th>
              {columns.map((c) => (
                <th key={c} className="px-1 py-1 text-muted font-medium align-bottom">
                  <span className="block max-w-[90px] truncate" title={c}>
                    {c}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {names.map((row) => {
              const cells = confusion[row] || {};
              const rowTotal = Object.values(cells).reduce((a: number, b: any) => a + (b as number), 0) || 1;
              return (
                <tr key={row}>
                  <td className="px-2 py-1 text-primary whitespace-nowrap">
                    <code>{row}</code>
                  </td>
                  {columns.map((col) => {
                    const n = (cells[col] as number) || 0;
                    const share = n / rowTotal;
                    const diagonal = row === col;
                    return (
                      <td
                        key={col}
                        className={cn("w-14 h-8 text-center tabular-nums rounded", diagonal ? "font-semibold text-primary" : "text-t-hover")}
                        style={{
                          backgroundColor: n
                            ? diagonal
                              ? `rgba(12, 163, 12, ${0.12 + 0.5 * share})`
                              : `rgba(208, 59, 59, ${0.1 + 0.55 * share})`
                            : "var(--surface-50)",
                        }}
                        title={`${row} → ${col}: ${n} (${formatPct(share)})`}
                      >
                        {n || ""}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] text-muted mt-2">Green diagonal = correct · red = confusions.</p>
    </SectionCard>
  );
}

/* ═══════════════════════════ Predictions explorer ═══════════════════════════ */

function PredictionsExplorer({
  comparisonId,
  models,
  labels,
  difficulties,
  refreshKey,
}: {
  comparisonId: number;
  models: any[];
  labels: any[];
  difficulties: string[];
  refreshKey: number;
}) {
  const [modelId, setModelId] = useState<number | "">(models[0]?.id ?? "");
  const [outcome, setOutcome] = useState("errors");
  const [expected, setExpected] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [data, setData] = useState<{ total: number; items: any[] }>({ total: 0, items: [] });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    api
      .listComparisonPredictions(comparisonId, {
        model_result_id: modelId === "" ? undefined : modelId,
        outcome: outcome || undefined,
        expected_label: expected || undefined,
        difficulty: difficulty || undefined,
        search: search || undefined,
        offset: page * PRED_PAGE,
        limit: PRED_PAGE,
      })
      .then(setData)
      .catch(() => setData({ total: 0, items: [] }))
      .finally(() => setLoading(false));
  }, [comparisonId, modelId, outcome, expected, difficulty, search, page, refreshKey]);

  const byId = Object.fromEntries(models.map((m) => [m.id, m]));
  const pages = Math.max(1, Math.ceil(data.total / PRED_PAGE));
  const reset = () => setPage(0);

  return (
    <SectionCard
      title="Predictions"
      description={`${formatInt(data.total)} matching prediction${data.total === 1 ? "" : "s"} — inspect exactly where each model went wrong.`}
      actions={loading ? <Loader2 className="w-4 h-4 animate-spin text-muted" /> : undefined}
    >
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <select
          value={modelId}
          onChange={(e) => {
            setModelId(e.target.value === "" ? "" : Number(e.target.value));
            reset();
          }}
          className="bg-surface-50 border border-visible rounded-lg px-2 py-1.5 text-xs text-primary focus:outline-none focus:border-accent/50"
        >
          <option value="">All models</option>
          {models.map((m) => (
            <option key={m.id} value={m.id}>
              {m.display_name}
            </option>
          ))}
        </select>
        <div className="flex rounded-lg border border-visible overflow-hidden text-xs">
          {[
            ["", "All"],
            ["correct", "Correct"],
            ["errors", "Errors"],
            ["incorrect", "Wrong label"],
            ["failed", "No answer"],
          ].map(([value, label]) => (
            <button
              key={value}
              onClick={() => {
                setOutcome(value);
                reset();
              }}
              className={cn("px-2.5 py-1.5 transition-colors", outcome === value ? "bg-accent/20 text-accent" : "text-t-secondary hover:text-primary")}
            >
              {label}
            </button>
          ))}
        </div>
        <select
          value={expected}
          onChange={(e) => {
            setExpected(e.target.value);
            reset();
          }}
          className="bg-surface-50 border border-visible rounded-lg px-2 py-1.5 text-xs text-primary focus:outline-none focus:border-accent/50"
        >
          <option value="">Any expected label</option>
          {labels.map((l: any) => (
            <option key={l.name} value={l.name}>
              {l.name}
            </option>
          ))}
        </select>
        {difficulties.length > 0 && (
          <select
            value={difficulty}
            onChange={(e) => {
              setDifficulty(e.target.value);
              reset();
            }}
            className="bg-surface-50 border border-visible rounded-lg px-2 py-1.5 text-xs text-primary focus:outline-none focus:border-accent/50"
          >
            <option value="">Any difficulty</option>
            {difficulties.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        )}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setSearch(searchInput.trim());
            reset();
          }}
          className="relative"
        >
          <Search className="w-3.5 h-3.5 text-muted absolute left-2 top-1/2 -translate-y-1/2" />
          <input
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search text…"
            className="pl-7 pr-2 py-1.5 w-48 bg-surface-50 border border-visible rounded-lg text-xs text-primary placeholder-muted focus:outline-none focus:border-accent/50"
          />
        </form>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-[10px] uppercase tracking-wider text-muted border-b border-visible">
              <th className="py-2 pr-3 font-medium">Text</th>
              <th className="py-2 pr-3 font-medium">Model</th>
              <th className="py-2 pr-3 font-medium">Expected</th>
              <th className="py-2 pr-3 font-medium">Predicted</th>
              <th className="py-2 pr-3 font-medium text-right">Confidence</th>
              <th className="py-2 pr-3 font-medium text-right">Latency</th>
              <th className="py-2 font-medium text-right">Cost</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[color:var(--input-border)]">
            {data.items.map((p) => {
              const m = byId[p.model_result_id];
              return (
                <tr key={p.id} className="align-top">
                  <td className="py-2 pr-3 text-primary text-[12px] leading-snug max-w-xl">{p.text}</td>
                  <td className="py-2 pr-3 whitespace-nowrap">
                    <span className="inline-flex items-center gap-1.5 text-t-hover">
                      {m && <SeriesDot color={m.color} />}
                      {m ? shortName(m) : p.model_result_id}
                    </span>
                  </td>
                  <td className="py-2 pr-3">
                    <code className="text-primary">{p.expected_label}</code>
                  </td>
                  <td className="py-2 pr-3">
                    {p.status === "ok" ? (
                      <span className="inline-flex items-center gap-1">
                        <span aria-hidden className={p.is_correct ? "text-success" : "text-danger"}>
                          {p.is_correct ? "✓" : "✗"}
                        </span>
                        <code className="text-primary">{p.predicted_label}</code>
                      </span>
                    ) : (
                      <span className="text-warning" title={p.raw_output || ""}>
                        ⚠ {p.status === "error" ? "error" : "no valid label"}
                        {p.error && <span className="block text-[10px] text-muted max-w-[220px] truncate">{p.error}</span>}
                      </span>
                    )}
                  </td>
                  <td
                    className="py-2 pr-3 text-right tabular-nums text-t-hover"
                    title={
                      p.probabilities
                        ? Object.entries(p.probabilities)
                            .sort((a: any, b: any) => b[1] - a[1])
                            .map(([k, v]: any) => `${k}: ${formatPct(v, 1)}`)
                            .join("\n")
                        : undefined
                    }
                  >
                    {p.confidence === null ? "—" : formatPct(p.confidence, 0)}
                  </td>
                  <td className="py-2 pr-3 text-right tabular-nums text-t-hover whitespace-nowrap">
                    {formatMs(p.latency_ms)}
                    {p.attempts > 1 && <span className="block text-[10px] text-muted">{p.attempts} attempts</span>}
                  </td>
                  <td className="py-2 text-right tabular-nums text-t-hover">{formatCost(p.cost)}</td>
                </tr>
              );
            })}
            {data.items.length === 0 && (
              <tr>
                <td colSpan={7} className="py-8 text-center text-sm text-muted">
                  {loading ? "Loading…" : "No predictions match these filters."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <Pager page={page} pages={pages} onChange={setPage} />
    </SectionCard>
  );
}
