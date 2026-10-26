"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AlertCircle, Check, Loader2, Play, Plus, Scale, Settings, X, Zap, Brain } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { KindBadge, SectionCard, SeriesDot, formatCost, formatInt, useSeriesColors } from "./shared";

const MAX_MODELS = 8;
const SAMPLE_PRESETS = [100, 250, 500, 1000];

interface SelectedModel {
  key: string;
  kind: "decision" | "llm";
  provider_id: number;
  provider_name: string;
  provider_type: string;
  model: string;
  display_name: string;
  input_price: string;
  output_price: string;
  pricing_source: string;
}

const modelKey = (m: { kind: string; provider_id: number; model: string }) => `${m.kind}:${m.provider_id}:${m.model}`;

const toPrice = (v: number | null | undefined) => (v === null || v === undefined ? "" : String(v));

export default function DecisionCompare() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const colors = useSeriesColors();

  const [datasets, setDatasets] = useState<any[]>([]);
  const [available, setAvailable] = useState<{ decision_models: any[]; llm_models: any[] }>({ decision_models: [], llm_models: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [datasetId, setDatasetId] = useState<number | null>(null);
  const [sampleMode, setSampleMode] = useState<"preset" | "all" | "custom">("preset");
  const [samplePreset, setSamplePreset] = useState(250);
  const [customSample, setCustomSample] = useState("");
  const [sampling, setSampling] = useState("stratified");
  const [selected, setSelected] = useState<SelectedModel[]>([]);
  const [name, setName] = useState("");
  const [concurrency, setConcurrency] = useState(8);
  const [temperature, setTemperature] = useState(0);
  const [seed, setSeed] = useState(42);

  const [estimate, setEstimate] = useState<any>(null);
  const [estimating, setEstimating] = useState(false);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    Promise.all([api.listDecisionDatasets(), api.listComparableModels()])
      .then(([ds, models]) => {
        setDatasets(ds);
        setAvailable(models);
        const fromUrl = Number(searchParams.get("dataset"));
        const initial = ds.find((d: any) => d.id === fromUrl) || ds[0];
        if (initial) setDatasetId(initial.id);
        // Sensible default: the first decision model + the first two LLMs.
        const defaults = [...models.decision_models.slice(0, 1), ...models.llm_models.slice(0, 2)];
        setSelected(defaults.map(toSelected));
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const dataset = datasets.find((d) => d.id === datasetId);

  const sampleSize: number | null = useMemo(() => {
    if (sampleMode === "all") return null;
    if (sampleMode === "custom") {
      const n = parseInt(customSample, 10);
      return Number.isFinite(n) && n > 0 ? n : null;
    }
    return samplePreset;
  }, [sampleMode, samplePreset, customSample]);

  const effectiveItems = dataset ? Math.min(sampleSize ?? dataset.item_count, dataset.item_count) : 0;

  const payloadModels = useMemo(
    () =>
      selected.map((m) => ({
        kind: m.kind,
        provider_id: m.provider_id,
        model: m.model,
        display_name: m.display_name,
        input_price_per_million: m.input_price === "" ? null : Number(m.input_price),
        output_price_per_million: m.output_price === "" ? null : Number(m.output_price),
      })),
    [selected]
  );

  // Live cost projection, debounced.
  useEffect(() => {
    if (!datasetId || selected.length === 0) {
      setEstimate(null);
      return;
    }
    const handle = setTimeout(() => {
      setEstimating(true);
      api
        .estimateComparison({ dataset_id: datasetId, models: payloadModels, sample_size: sampleSize, sampling, seed })
        .then(setEstimate)
        .catch(() => setEstimate(null))
        .finally(() => setEstimating(false));
    }, 400);
    return () => clearTimeout(handle);
  }, [datasetId, payloadModels, sampleSize, sampling, seed, selected.length]);

  const toggle = (m: any) => {
    const key = modelKey(m);
    setSelected((prev) => {
      if (prev.some((s) => s.key === key)) return prev.filter((s) => s.key !== key);
      if (prev.length >= MAX_MODELS) return prev;
      return [...prev, toSelected(m)];
    });
  };

  const updatePrice = (key: string, field: "input_price" | "output_price", value: string) => {
    setSelected((prev) => prev.map((s) => (s.key === key ? { ...s, [field]: value } : s)));
  };

  const start = async () => {
    if (!datasetId || selected.length === 0) return;
    setStarting(true);
    setError(null);
    try {
      const comp = await api.createComparison({
        name: name.trim() || undefined,
        dataset_id: datasetId,
        models: payloadModels,
        sample_size: sampleSize,
        sampling,
        seed,
        concurrency,
        temperature,
      });
      router.push(`/?view=decision-results&comparison=${comp.id}`);
    } catch (e: any) {
      setError(e.message);
      setStarting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 text-accent animate-spin" />
      </div>
    );
  }

  const noDecisionProviders = available.decision_models.length === 0;
  const noModels = noDecisionProviders && available.llm_models.length === 0;
  const unknownPrices = selected.filter((m) => m.input_price === "" && m.output_price === "");

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-accent/15 flex items-center justify-center">
          <Scale className="w-5 h-5 text-accent" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-primary">Compare Decision Models vs LLMs</h2>
          <p className="text-sm text-t-secondary">
            Run the same labeled sample through Jev-style decision models and LLM classifiers, then compare
            accuracy, errors and total cost.
          </p>
        </div>
      </div>

      {error && (
        <div className="flex items-start gap-2 px-4 py-3 bg-danger/10 border border-danger/20 rounded-xl text-danger text-sm">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <span className="flex-1">{error}</span>
          <button onClick={() => setError(null)}>
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* 1 — Dataset */}
      <SectionCard title="1. Dataset" description="Pick a built-in dataset or one you uploaded.">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 space-y-2">
            <select
              value={datasetId ?? ""}
              onChange={(e) => setDatasetId(Number(e.target.value))}
              className="w-full px-3 py-2 bg-surface-50 border border-visible rounded-lg text-primary text-sm focus:outline-none focus:border-accent/50"
            >
              {datasets.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} — {formatInt(d.item_count)} rows · {d.labels.length} labels{d.is_builtin ? "" : " (custom)"}
                </option>
              ))}
            </select>
            {dataset && (
              <div className="bg-surface-50 border border-visible rounded-lg px-3 py-2">
                <p className="text-[11px] uppercase tracking-wider text-muted">Task</p>
                <p className="text-sm text-primary">{dataset.task}</p>
                <div className="flex flex-wrap gap-1 mt-2">
                  {dataset.labels.slice(0, 16).map((l: any) => (
                    <code key={l.name} className="px-1.5 py-0.5 rounded bg-surface-200 text-[11px] text-t-hover">
                      {l.name}
                    </code>
                  ))}
                  {dataset.labels.length > 16 && <span className="text-[11px] text-muted">+{dataset.labels.length - 16} more</span>}
                </div>
              </div>
            )}
            <button
              onClick={() => router.push("/?view=decision-datasets")}
              className="text-xs text-accent hover:underline"
            >
              Browse or upload datasets →
            </button>
          </div>
          <div className="space-y-3">
            <div>
              <span className="block text-xs font-medium text-t-hover mb-1.5">Sample size</span>
              <div className="flex flex-wrap gap-1.5">
                {SAMPLE_PRESETS.map((n) => (
                  <Chip key={n} active={sampleMode === "preset" && samplePreset === n} onClick={() => { setSampleMode("preset"); setSamplePreset(n); }}>
                    {formatInt(n)}
                  </Chip>
                ))}
                <Chip active={sampleMode === "all"} onClick={() => setSampleMode("all")}>
                  All
                </Chip>
                <Chip active={sampleMode === "custom"} onClick={() => setSampleMode("custom")}>
                  Custom
                </Chip>
              </div>
              {sampleMode === "custom" && (
                <input
                  type="number"
                  min={1}
                  value={customSample}
                  onChange={(e) => setCustomSample(e.target.value)}
                  placeholder="Number of rows"
                  className="mt-2 w-full px-3 py-1.5 bg-surface-50 border border-visible rounded-lg text-primary text-sm focus:outline-none focus:border-accent/50"
                />
              )}
              <p className="text-[11px] text-muted mt-1.5">
                {formatInt(effectiveItems)} rows × {selected.length} model{selected.length === 1 ? "" : "s"} ={" "}
                {formatInt(effectiveItems * selected.length)} requests
              </p>
            </div>
            <div>
              <span className="block text-xs font-medium text-t-hover mb-1.5">Sampling</span>
              <select
                value={sampling}
                onChange={(e) => setSampling(e.target.value)}
                className="w-full px-3 py-1.5 bg-surface-50 border border-visible rounded-lg text-primary text-sm focus:outline-none focus:border-accent/50"
              >
                <option value="stratified">Stratified — keep the label mix</option>
                <option value="random">Random</option>
                <option value="first">First rows</option>
              </select>
            </div>
          </div>
        </div>
      </SectionCard>

      {/* 2 — Models */}
      <SectionCard
        title="2. Models"
        description={`Select up to ${MAX_MODELS}. Every model sees the same rows, task question and label definitions.`}
      >
        {noModels ? (
          <EmptyProviders onOpenSettings={() => router.push("/?view=settings")} />
        ) : (
          <div className="space-y-5">
            <ModelPicker
              title="Decision models"
              icon={Zap}
              hint="Typed choice + probability — TypeSafe Jev, OpenAI's Decisions API and System One-compatible endpoints."
              models={available.decision_models}
              selected={selected}
              onToggle={toggle}
              empty={
                <div className="flex flex-wrap items-center gap-3 text-xs text-t-secondary bg-warning/5 border border-warning/20 rounded-lg px-3 py-2.5">
                  <Zap className="w-4 h-4 text-warning" />
                  <span className="flex-1">
                    No decision provider yet. Add <strong className="text-primary">TypeSafe (Jev)</strong>, select{" "}
                    <strong className="text-primary">gpt-6-luna</strong> under Decision Models on an OpenAI provider, or add
                    any System One-compatible endpoint in Settings → Providers.
                  </span>
                  <button
                    onClick={() => router.push("/?view=settings")}
                    className="flex items-center gap-1 px-2.5 py-1 rounded-md border border-visible text-primary hover:bg-surface-200/50"
                  >
                    <Settings className="w-3 h-3" /> Providers
                  </button>
                </div>
              }
            />
            <ModelPicker
              title="LLMs"
              icon={Brain}
              hint="Prompted to answer with exactly one label as JSON."
              models={available.llm_models}
              selected={selected}
              onToggle={toggle}
              empty={<p className="text-xs text-muted">No LLM providers configured.</p>}
            />

            {selected.length > 0 && (
              <div>
                <div className="flex items-baseline justify-between mb-2">
                  <span className="text-xs font-medium text-t-hover">Selected models & pricing</span>
                  <span className="text-[11px] text-muted">USD per 1M tokens — edit to match your contract</span>
                </div>
                <div className="border border-visible rounded-xl divide-y divide-[color:var(--input-border)]">
                  {selected.map((m, idx) => (
                    <div key={m.key} className="flex flex-wrap items-center gap-3 px-3 py-2.5">
                      <SeriesDot color={colors[idx]} />
                      <div className="flex-1 min-w-[180px]">
                        <div className="flex items-center gap-2">
                          <span className="text-sm text-primary font-medium">{m.model}</span>
                          <KindBadge kind={m.kind} />
                        </div>
                        <span className="text-[11px] text-muted">{m.provider_name}</span>
                      </div>
                      <PriceInput label="Input" value={m.input_price} onChange={(v) => updatePrice(m.key, "input_price", v)} />
                      <PriceInput label="Output" value={m.output_price} onChange={(v) => updatePrice(m.key, "output_price", v)} />
                      <span className={cn("text-[11px] w-28", m.input_price === "" && m.output_price === "" ? "text-warning" : "text-muted")}>
                        {m.input_price === "" && m.output_price === "" ? "Price unknown" : m.pricing_source}
                      </span>
                      <button
                        onClick={() => setSelected((prev) => prev.filter((s) => s.key !== m.key))}
                        className="p-1 rounded-md hover:bg-surface-200/60"
                        aria-label={`Remove ${m.model}`}
                      >
                        <X className="w-3.5 h-3.5 text-muted" />
                      </button>
                    </div>
                  ))}
                </div>
                {unknownPrices.length > 0 && (
                  <p className="text-[11px] text-warning mt-1.5">
                    {unknownPrices.length} model{unknownPrices.length > 1 ? "s have" : " has"} no known price — its total cost will
                    show as “—”. Enter a price (or 0 for self-hosted) to include it.
                  </p>
                )}
              </div>
            )}
          </div>
        )}
      </SectionCard>

      {/* 3 — Run settings */}
      <SectionCard title="3. Run settings">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <label className="block md:col-span-2">
            <span className="block text-xs font-medium text-t-hover mb-1">Comparison name</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={dataset ? `${dataset.name} — ${selected.length} models` : "My comparison"}
              className="w-full px-3 py-2 bg-surface-50 border border-visible rounded-lg text-primary placeholder-muted text-sm focus:outline-none focus:border-accent/50"
            />
          </label>
          <label className="block">
            <span className="block text-xs font-medium text-t-hover mb-1">Parallel requests per model</span>
            <input
              type="number"
              min={1}
              max={32}
              value={concurrency}
              onChange={(e) => setConcurrency(Math.max(1, Math.min(32, Number(e.target.value) || 1)))}
              className="w-full px-3 py-2 bg-surface-50 border border-visible rounded-lg text-primary text-sm focus:outline-none focus:border-accent/50"
            />
          </label>
          <label className="block">
            <span className="block text-xs font-medium text-t-hover mb-1">LLM temperature</span>
            <input
              type="number"
              min={0}
              max={2}
              step={0.1}
              value={temperature}
              onChange={(e) => setTemperature(Math.max(0, Math.min(2, Number(e.target.value) || 0)))}
              className="w-full px-3 py-2 bg-surface-50 border border-visible rounded-lg text-primary text-sm focus:outline-none focus:border-accent/50"
            />
          </label>
        </div>
        <label className="block mt-3 w-40">
          <span className="block text-xs font-medium text-t-hover mb-1">Sampling seed</span>
          <input
            type="number"
            value={seed}
            onChange={(e) => setSeed(Number(e.target.value) || 0)}
            className="w-full px-3 py-1.5 bg-surface-50 border border-visible rounded-lg text-primary text-sm focus:outline-none focus:border-accent/50"
          />
        </label>
      </SectionCard>

      {/* Estimate + start */}
      <div className="bg-surface-100 rounded-2xl border border-visible p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex-1 min-w-[280px]">
            <h3 className="text-sm font-semibold text-primary flex items-center gap-2">
              Projected cost
              {estimating && <Loader2 className="w-3.5 h-3.5 animate-spin text-muted" />}
            </h3>
            <p className="text-xs text-t-secondary mt-0.5">Estimated from text length (≈4 characters per token). Actual usage is measured during the run.</p>
            {estimate && (
              <table className="w-full text-xs mt-3">
                <thead>
                  <tr className="text-left text-[10px] uppercase tracking-wider text-muted">
                    <th className="py-1 font-medium">Model</th>
                    <th className="py-1 font-medium text-right">Input tokens</th>
                    <th className="py-1 font-medium text-right">Output tokens</th>
                    <th className="py-1 font-medium text-right">Est. cost</th>
                  </tr>
                </thead>
                <tbody>
                  {estimate.models.map((m: any, idx: number) => (
                    <tr key={idx} className="border-t border-[color:var(--input-border)]">
                      <td className="py-1.5 text-primary">
                        <span className="inline-flex items-center gap-2">
                          <SeriesDot color={colors[idx]} />
                          {m.model}
                        </span>
                      </td>
                      <td className="py-1.5 text-right tabular-nums text-t-hover">{formatInt(m.input_tokens)}</td>
                      <td className="py-1.5 text-right tabular-nums text-t-hover">{formatInt(m.output_tokens)}</td>
                      <td className="py-1.5 text-right tabular-nums text-primary font-medium">{formatCost(m.estimated_cost)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div className="flex flex-col items-end gap-2">
            <div className="text-right">
              <p className="text-[11px] uppercase tracking-wider text-muted">Estimated total</p>
              <p className="text-2xl font-semibold text-primary">{formatCost(estimate?.estimated_total_cost)}</p>
              <p className="text-[11px] text-t-secondary">{formatInt(estimate?.requests ?? 0)} requests</p>
            </div>
            <button
              onClick={start}
              disabled={starting || !datasetId || selected.length === 0}
              className="flex items-center gap-2 px-6 py-2.5 bg-accent text-accent-foreground rounded-xl text-sm font-semibold hover:bg-accent/90 transition-colors disabled:opacity-50"
            >
              {starting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
              Run comparison
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function toSelected(m: any): SelectedModel {
  return {
    key: modelKey(m),
    kind: m.kind,
    provider_id: m.provider_id,
    provider_name: m.provider_name,
    provider_type: m.provider_type,
    model: m.model,
    display_name: m.display_name ?? `${m.model} (${m.provider_name})`,
    input_price: toPrice(m.input_price_per_million),
    output_price: toPrice(m.output_price_per_million),
    pricing_source: m.pricing_source,
  };
}

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "px-2.5 py-1 rounded-lg text-xs border transition-colors",
        active
          ? "bg-accent/20 border-accent text-accent"
          : "bg-surface-50 border-visible text-t-hover hover:text-primary hover:border-accent/50"
      )}
    >
      {children}
    </button>
  );
}

function PriceInput({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="flex items-center gap-1.5 text-[11px] text-muted">
      {label}
      <span className="relative">
        <span className="absolute left-2 top-1/2 -translate-y-1/2 text-muted">$</span>
        <input
          type="number"
          min={0}
          step="0.001"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="?"
          className="w-24 pl-5 pr-2 py-1 bg-surface-50 border border-visible rounded-md text-primary text-xs tabular-nums focus:outline-none focus:border-accent/50"
        />
      </span>
    </label>
  );
}

function ModelPicker({
  title,
  icon: Icon,
  hint,
  models,
  selected,
  onToggle,
  empty,
}: {
  title: string;
  icon: any;
  hint: string;
  models: any[];
  selected: SelectedModel[];
  onToggle: (m: any) => void;
  empty: React.ReactNode;
}) {
  const full = selected.length >= MAX_MODELS;
  return (
    <div>
      <div className="flex items-center gap-2 mb-1">
        <Icon className="w-3.5 h-3.5 text-t-secondary" />
        <span className="text-xs font-semibold text-primary uppercase tracking-wider">{title}</span>
      </div>
      <p className="text-[11px] text-muted mb-2">{hint}</p>
      {models.length === 0 ? (
        empty
      ) : (
        <div className="flex flex-wrap gap-2">
          {models.map((m) => {
            const isSelected = selected.some((s) => s.key === modelKey(m));
            return (
              <button
                key={modelKey(m)}
                onClick={() => onToggle(m)}
                disabled={!isSelected && full}
                className={cn(
                  "px-3 py-1.5 rounded-lg text-sm border transition-colors disabled:opacity-40",
                  isSelected
                    ? "bg-accent/20 border-accent text-accent"
                    : "bg-surface-50 border-visible text-t-hover hover:text-primary hover:border-accent/50"
                )}
              >
                {isSelected ? <Check className="w-3 h-3 inline mr-1" /> : <Plus className="w-3 h-3 inline mr-1 opacity-60" />}
                {m.model}
                <span className="text-xs text-muted ml-1">({m.provider_name})</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function EmptyProviders({ onOpenSettings }: { onOpenSettings: () => void }) {
  return (
    <div className="text-center py-8">
      <Scale className="w-10 h-10 text-muted mx-auto mb-3" />
      <p className="text-sm text-primary font-medium">No models available yet</p>
      <p className="text-xs text-t-secondary mt-1 max-w-md mx-auto">
        Add a decision-model provider (TypeSafe Jev or OpenAI's Decisions API) and at least one LLM provider in Settings → Providers.
      </p>
      <button
        onClick={onOpenSettings}
        className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-accent text-accent-foreground rounded-lg text-sm font-medium hover:bg-accent/90"
      >
        <Settings className="w-4 h-4" /> Open Providers
      </button>
    </div>
  );
}
